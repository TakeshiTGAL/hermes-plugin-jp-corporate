"""HTTP client for the gBizINFO REST API v2 (https://info.gbiz.go.jp/).

Standard library only. The token is read from the environment on every request
and is sent only to the gBizINFO API host, in the X-hojinInfo-api-token header.

gBizINFO is a free government API whose terms forbid excessive or bulk access,
so the client is deliberately conservative: it spaces requests out, keeps a
short in-memory cache (nothing is written to disk), never retries in a loop,
and never paginates on its own.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

API_BASE = "https://api.info.gbiz.go.jp/hojin/v2/hojin"
TOKEN_ENV = "GBIZINFO_API_TOKEN"
APPLY_URL = "https://info.gbiz.go.jp/hojin/various_registration/form"
VERSION = "0.1.0"
USER_AGENT = f"hermes-plugin-jp-corporate/{VERSION}"
TIMEOUT_SECONDS = 20
MIN_INTERVAL_SECONDS = 0.5
CACHE_TTL_SECONDS = 600
CACHE_MAX_ENTRIES = 256

TOKEN_HELP = (
    f"{TOKEN_ENV} is not set. gBizINFO needs a free personal API token: apply at {APPLY_URL} "
    "(申請区分「トークン利用(WebAPI・データダウンロード)」), open the link in the "
    "「Web API 利用申請完了」 email to see the token, add "
    f"{TOKEN_ENV}=<token> to ~/.hermes/.env, then restart Hermes. "
    "Apply once and keep using that token: the API terms forbid getting or using extra tokens to get "
    "around usage limits."
)


class ApiError(Exception):
    """gBizINFO rejected the request or could not be reached. The message says what to do next."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class NotFound(ApiError):
    """gBizINFO answered 404: no corporation matched."""


_lock = threading.Lock()
_last_request_at = 0.0
_cache: dict[str, tuple[float, dict]] = {}
_calls = threading.local()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: urllib would otherwise resend the token header to the new host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _open(request):
    return _OPENER.open(request, timeout=TIMEOUT_SECONDS)


def reset_request_count() -> None:
    _calls.count = 0


def request_count() -> int:
    """Requests actually sent to gBizINFO by this thread since the last reset (cache hits excluded)."""
    return getattr(_calls, "count", 0)


def token_configured() -> bool:
    return bool(os.environ.get(TOKEN_ENV, "").strip())


def get(path: str = "", params: dict | None = None) -> dict:
    """GET one API route (relative to /v2/hojin) and return the decoded JSON.

    Raises NotFound on 404 (gBizINFO's answer for "no match") and ApiError for
    everything else that is not a 200.
    """
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise ApiError(TOKEN_HELP)
    # The API answers 500 when a path ends with "/", so build it without one.
    url = API_BASE + (f"/{path.strip('/')}" if path.strip("/") else "")
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})

    now = time.monotonic()
    with _lock:
        hit = _cache.get(url)
        if hit and now - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]

    _calls.count = request_count() + 1
    data = _request(url, token)

    with _lock:
        if len(_cache) >= CACHE_MAX_ENTRIES:
            _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
        _cache[url] = (time.monotonic(), data)
    return data


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _throttle() -> None:
    """Keep at least MIN_INTERVAL_SECONDS between requests, across threads."""
    global _last_request_at
    with _lock:
        slot = max(time.monotonic(), _last_request_at + MIN_INTERVAL_SECONDS)
        _last_request_at = slot
    wait = slot - time.monotonic()
    if wait > 0:
        time.sleep(wait)


def _request(url: str, token: str) -> dict:
    _throttle()
    request = urllib.request.Request(
        url,
        headers={"X-hojinInfo-api-token": token, "Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with _open(request) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise _http_error(error.code) from None
    except urllib.error.URLError as error:
        raise ApiError(
            f"Could not reach gBizINFO ({error.reason}). Check the network connection and try again in a "
            "minute; scheduled maintenance is announced at https://info.gbiz.go.jp/."
        ) from None
    except TimeoutError:
        raise ApiError("gBizINFO did not answer within 20 seconds. Try again in a minute.") from None
    try:
        return json.loads(body)
    except ValueError:
        raise ApiError(
            "gBizINFO returned something that is not JSON (often a maintenance page). "
            "Try again later; maintenance is announced at https://info.gbiz.go.jp/."
        ) from None


def _http_error(status: int) -> ApiError:
    if 300 <= status < 400:
        return ApiError(
            f"gBizINFO answered with a redirect ({status}). It was not followed, so the token was not sent "
            "anywhere else. The API address may have changed: check https://info.gbiz.go.jp/ and update the plugin.",
            status,
        )
    if status == 404:
        return NotFound("not found", status)
    if status == 401:
        return ApiError(
            f"gBizINFO rejected the API token (401). Check that {TOKEN_ENV} in ~/.hermes/.env is the exact "
            "token shown by the link in your 「Web API 利用申請完了」 email (no quotes or spaces), then restart "
            "Hermes. If the token was revoked, contact gBizINFO via https://help.info.gbiz.go.jp/hc/ja/requests/new "
            "rather than applying for a second token.",
            status,
        )
    if status in (403, 429):
        return ApiError(
            f"gBizINFO is limiting requests from this token ({status}). Stop and wait several minutes before "
            "the next lookup, and avoid calling the tools in a loop: the API terms allow suspending tokens "
            "that send excessive requests. For bulk data use gBizINFO's download files instead.",
            status,
        )
    if status == 400:
        return ApiError("gBizINFO rejected the request parameters (400). Re-check the name or address you sent.", status)
    return ApiError(
        f"gBizINFO returned HTTP {status}. This is usually maintenance or a temporary fault: try again later "
        "(maintenance is announced at https://info.gbiz.go.jp/).",
        status,
    )

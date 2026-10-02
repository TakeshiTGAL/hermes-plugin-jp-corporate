"""Load the repo root as a package (the way Hermes loads a plugin directory) and replay recorded API answers.

The fixtures under tests/fixtures are gBizINFO v2 responses recorded on 2026-10-02 and
trimmed to the fields the tests use (see tests/fixtures/README.md). No test sends a
network request: sockets are blocked.
"""

import importlib.util
import json
import socket
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
PACKAGE = "jp_corporate_plugin"
FAKE_TOKEN = "test-token-abcdef-not-real"


def _load_plugin():
    spec = importlib.util.spec_from_file_location(
        PACKAGE, PLUGIN_DIR / "__init__.py", submodule_search_locations=[str(PLUGIN_DIR)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE] = module
    spec.loader.exec_module(module)
    return module


# The repo root is the plugin package, and pytest also imports a root __init__.py while it
# sets up the test session. The directory name (hermes-plugin-jp-corporate) is not a valid
# package name, so pytest would import it as a bare "__init__" module and its relative
# imports would fail. Hand pytest the copy loaded above instead.
PLUGIN = sys.modules.get(PACKAGE) or _load_plugin()
sys.modules.setdefault("__init__", PLUGIN)


@pytest.fixture(scope="session")
def plugin():
    return PLUGIN


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("a test tried to open a real network connection")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body
        self.status = 200

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeApi:
    """Stands in for client._open. Routes /v2/hojin URLs to fixture files."""

    def __init__(self):
        self.requests = []  # (url, headers)
        self.status_override = None

    def route(self, url: str) -> tuple[int, str]:
        parsed = urllib.parse.urlparse(url)
        assert parsed.netloc == "api.info.gbiz.go.jp", parsed.netloc
        path = parsed.path.removeprefix("/hojin/v2/hojin")
        query = urllib.parse.parse_qs(parsed.query)
        if path == "":
            name = query.get("name", [""])[0]
            fixture = {"トヨタ自動車": "search_name_toyota"}.get(name)
            return (200, fixture) if fixture else (404, "search_not_found")
        parts = path.strip("/").split("/")
        fixture = "hojin_" + "_".join(parts)
        if (FIXTURES / f"{fixture}.json").exists():
            return 200, fixture
        return 404, "search_not_found"

    def __call__(self, request):
        url = request.full_url
        self.requests.append((url, dict(request.header_items())))
        status, fixture = self.route(url)
        if self.status_override:
            status, fixture = self.status_override, "unauthorized"
        body = (FIXTURES / f"{fixture}.json").read_bytes()
        if status != 200:
            raise urllib.error.HTTPError(url, status, "error", {}, None)
        return FakeResponse(body)

    def params(self, index=-1) -> dict:
        query = urllib.parse.urlparse(self.requests[index][0]).query
        return {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}


@pytest.fixture
def api(plugin, monkeypatch):
    fake = FakeApi()
    monkeypatch.setenv("GBIZINFO_API_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(plugin.client, "_open", fake)
    monkeypatch.setattr(plugin.client, "MIN_INTERVAL_SECONDS", 0)
    plugin.client.clear_cache()
    yield fake
    plugin.client.clear_cache()


def call(plugin, tool, args):
    return json.loads(plugin.tools.HANDLERS[tool](args))

"""Load the repo root as a package (the way Hermes loads a plugin directory) and replay recorded API answers.

The fixtures under tests/fixtures are gBizINFO v2 responses recorded on 2026-10-02 and
trimmed to the fields the tests use (see tests/fixtures/README.md). No test sends a
network request: sockets are blocked.
"""

import importlib.util
import json
import os
import socket
import sys
import types
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

_SCOPE_STANDIN = "_jp_corporate_scope_standin"


def _install_scope_standin() -> None:
    """Hermes is absent: let get_secret read this process's environment.

    The same shape as index-search's stand-in (commit e3303f6). Tests that need
    the real scope still call pytest.importorskip and skip this stand-in.
    """
    standin = types.ModuleType("agent.secret_scope")

    def get_secret(name, default=None):
        value = os.environ.get(name)
        return default if value is None else value

    standin.get_secret = get_secret
    standin.UnscopedSecretError = type("UnscopedSecretError", (RuntimeError,), {})
    standin.set_secret_scope = lambda mapping=None, **kwargs: None
    standin.reset_secret_scope = lambda token: None
    standin.set_multiplex_active = lambda active: None
    setattr(standin, _SCOPE_STANDIN, True)
    agent = sys.modules.get("agent")
    if agent is None:
        agent = types.ModuleType("agent")
        sys.modules["agent"] = agent
    sys.modules["agent.secret_scope"] = standin
    setattr(agent, "secret_scope", standin)


try:
    import agent.secret_scope as _real_scope
except ImportError:
    _real_scope = None
if _real_scope is None:
    _install_scope_standin()


@pytest.fixture(scope="session")
def plugin():
    return PLUGIN


@pytest.fixture(autouse=True)
def _reset_secret_scope():
    scope = sys.modules.get("agent.secret_scope")
    if scope is None:
        yield
        return
    scope.set_multiplex_active(False)
    token = scope.set_secret_scope(None)
    try:
        yield
    finally:
        try:
            scope.reset_secret_scope(token)
        except ValueError:
            pass
        scope.set_secret_scope(None)
        scope.set_multiplex_active(False)


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

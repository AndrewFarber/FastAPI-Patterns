import io
import json
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.clients import runtime_flags
from app.clients.runtime_flags import AppConfigFlags, RuntimeFlags
from app.config.features import FeatureSettings
from app.config.settings import get_settings
from app.dependencies.flags import RuntimeFlagsDep, get_appconfig_flags


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Stands in for AppConfig Agent: set "body" to a response, or "error" to an exception."""
    state: dict = {"body": b"{}", "error": None, "urls": []}

    def urlopen(url, timeout):
        state["urls"].append(url)
        if state["error"]:
            raise state["error"]
        return io.BytesIO(state["body"])

    monkeypatch.setattr(runtime_flags.urllib.request, "urlopen", urlopen)
    return state


@pytest.fixture
def flags_client() -> Iterator[None]:
    get_appconfig_flags.cache_clear()
    yield
    get_appconfig_flags.cache_clear()


def test_beta_users_from_env(test_env, monkeypatch):
    monkeypatch.setenv("FEATURES__BETA_USERS", '["user-123","user-456"]')
    features = get_settings().features
    assert features.beta_users == frozenset({"user-123", "user-456"})
    assert "user-123" in json.loads(features.model_dump_json())["beta_users"]


def test_runtime_flags_source_from_env(test_env, flags_client, monkeypatch, agent):
    monkeypatch.setenv("FEATURES__RUNTIME_FLAGS__APPLICATION", "orders-api")
    monkeypatch.setenv("FEATURES__RUNTIME_FLAGS__ENVIRONMENT", "staging")
    get_appconfig_flags().get()
    assert agent["urls"] == [
        "http://localhost:2772/applications/orders-api/environments/staging/configurations/runtime-flags"
    ]


@pytest.mark.parametrize("body", [
    b"not json",
    b'["payments_kill_switch"]',                               # array payload
    b'{"payments_kill_switch": true}',                         # plain bool instead of {"enabled": ...}
    b'{"payments_kill_switch": {"value": 1}}',                 # no "enabled"
])
def test_bad_payload_keeps_last_good_flags(agent, body):
    flags = AppConfigFlags("orders-api", "dev", "runtime-flags", retry_after_seconds=0)
    good = {"payments_kill_switch": {"enabled": True, "note": "x"}, "added_later": {"enabled": True}}
    agent["body"] = json.dumps(good).encode()
    assert flags.get().payments_kill_switch is True
    agent["body"] = body
    assert flags.get().payments_kill_switch is True


def test_agent_down_backs_off(agent):
    flags = AppConfigFlags("orders-api", "dev", "runtime-flags", retry_after_seconds=60)
    agent["error"] = ConnectionRefusedError()
    assert flags.get() == RuntimeFlags()                      # safe defaults
    agent["error"] = None
    assert flags.get() == RuntimeFlags()
    assert len(agent["urls"]) == 1                            # no second call while backing off


def test_route_without_appconfig_gets_defaults(test_env, flags_client, agent):
    app = FastAPI()

    @app.get("/flags")
    def flags(flags: RuntimeFlagsDep) -> RuntimeFlags:
        return flags

    assert TestClient(app).get("/flags").json() == RuntimeFlags().model_dump()
    assert agent["urls"] == []                                # no source configured: no agent calls


def test_static_flags_default_off():
    features = FeatureSettings()
    assert not features.new_checkout and not features.bulk_export and not features.beta_users

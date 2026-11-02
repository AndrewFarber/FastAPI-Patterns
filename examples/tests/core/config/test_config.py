import json
import os
import subprocess

import pytest
from pydantic import ValidationError

from app.core.config.auth import AuthSettings
from app.core.config.cors import CorsSettings
from app.core.config.settings import Settings, get_settings
from conftest import TEST_VALUES, clear_settings_env, make_test_env


def test_env_vars_load(test_env):
    s = get_settings()
    assert s.db.name == "shop_test" and s.auth.audiences == ["test-client"]


def test_make_test_env_encodes_json():
    env = make_test_env()
    assert env["DB__HOST"] == "localhost"
    assert json.loads(env["AUTH__AUDIENCES"]) == ["test-client"]


def test_typo_fails_startup(test_env, monkeypatch):
    monkeypatch.setenv("DB__POOL_SZIE", "50")
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="pool_szie"):
        get_settings()


def test_stale_field_rejected():
    with pytest.raises(ValidationError, match="redis"):
        Settings(**TEST_VALUES, redis={"url": "x"})


def test_prod_safety():
    with pytest.raises(ValidationError, match="debug"):
        Settings(**TEST_VALUES, app={"is_prd": True, "debug": True})


def test_dump_masks_secrets():
    assert '"password":"**********"' in Settings(**TEST_VALUES).model_dump_json()


def test_frozen():
    with pytest.raises(ValidationError):
        Settings(**TEST_VALUES).app.name = "x"


def test_cors():
    with pytest.raises(ValidationError, match="wildcard"):
        CorsSettings(allow_origins=["*"], allow_credentials=True)


def test_auth_cognito_values(test_env, monkeypatch):
    for key, value in {
        "AUTH__ISSUER": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_AbC123xyz",
        "AUTH__AUDIENCES": '["1example23456789"]',
        "AUTH__AUDIENCE_CLAIM": "client_id",
        "AUTH__REQUIRED_CLAIMS": '{"token_use": "access"}',
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    auth = get_settings().auth
    assert auth.required_claims == {"token_use": "access"}
    assert auth.resolved_jwks_url.endswith("/us-east-1_AbC123xyz/.well-known/jwks.json")


def test_auth_rejects_unsafe_values():
    with pytest.raises(ValidationError, match="https"):
        AuthSettings(issuer="http://x", audiences=["a"])
    with pytest.raises(ValidationError):
        AuthSettings(issuer="https://x", audiences=["a"], algorithms=["HS256"])
    with pytest.raises(ValidationError):
        AuthSettings(issuer="https://x", audiences=[])


def test_shell_quoted_json_list(test_env, monkeypatch):
    value = subprocess.run(
        ["bash", "-c", """V='["http://localhost:3000"]'; printf %s "$V" """],
        capture_output=True, text=True, check=True,
    ).stdout
    monkeypatch.setenv("CORS__ALLOW_ORIGINS", value)
    get_settings.cache_clear()
    assert get_settings().cors.allow_origins == ["http://localhost:3000"]


def test_developer_env_is_cleared(monkeypatch):
    monkeypatch.setenv("APP__IS_PRD", "true")
    monkeypatch.setenv("db__host", "prod-db")
    clear_settings_env(monkeypatch)
    assert "APP__IS_PRD" not in os.environ and "db__host" not in os.environ

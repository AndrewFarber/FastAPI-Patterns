import json
import os
import subprocess

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError

from app.core.config.db import PasswordAuth
from app.core.config.settings import Settings, get_settings
from conftest import TEST_VALUES, clear_settings_env


def test_settings_load_from_env_vars(test_env):
    assert get_settings().db.name == "shop_test"


def test_typo_fails_startup(test_env, monkeypatch):
    monkeypatch.setenv("DB__POOL_SZIE", "50")
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match="pool_szie"):
        get_settings()


def test_stale_field_is_rejected():
    with pytest.raises(ValidationError, match="redis"):
        Settings(**TEST_VALUES, redis={"url": "x"})


def test_prod_rejects_debug_and_password_auth():
    with pytest.raises(ValidationError, match="debug"):
        Settings(**TEST_VALUES, app={"is_prd": True, "debug": True})
    with pytest.raises(ValidationError, match="password DB auth"):
        Settings(**TEST_VALUES, app={"is_prd": True})


def test_dump_masks_secrets():
    assert (
        '"password":"**********"' in Settings(**TEST_VALUES).model_dump_json()
    )


def test_settings_are_frozen():
    with pytest.raises(ValidationError):
        Settings(**TEST_VALUES).app.name = "x"


def test_shell_quoted_json_list_parses(test_env, monkeypatch):
    value = subprocess.run(
        ["bash", "-c", """V='["http://localhost:3000"]'; printf %s "$V" """],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    monkeypatch.setenv("CORS__ALLOW_ORIGINS", value)
    get_settings.cache_clear()
    assert get_settings().cors.allow_origins == ["http://localhost:3000"]


def test_developer_env_is_cleared(monkeypatch):
    monkeypatch.setenv("APP__IS_PRD", "true")
    monkeypatch.setenv("db__host", "prod-db")
    clear_settings_env(monkeypatch)
    assert "APP__IS_PRD" not in os.environ and "db__host" not in os.environ


def test_aws_sources_merge_secret_and_parameters(monkeypatch):
    with mock_aws():
        boto3.client("secretsmanager").create_secret(
            Name="shop/prd/app",
            SecretString=json.dumps({"db--auth--password": "p@ss"}),
        )
        ssm = boto3.client("ssm")
        for name, value in {
            "/shop/prd/db/host": "rds",
            "/shop/prd/db/user": "shop_app",
            "/shop/prd/db/name": "shop",
            "/shop/prd/db/sslmode": "disable",
            "/shop/prd/db/auth/method": "password",
            "/shop/prd/events/topic_arn": (
                "arn:aws:sns:us-east-1:123456789012:shop-events"
            ),
            "/shop/prd/switches/region": "us-east-1",
            "/shop/prd/switches/orders_paused": "/shop/switches/orders-paused",
        }.items():
            ssm.put_parameter(Name=name, Value=value, Type="String")
        monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "shop/prd/app")
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")

        settings = Settings()
        assert isinstance(settings.db.auth, PasswordAuth)
        assert settings.db.auth.password.get_secret_value() == "p@ss"

        monkeypatch.setenv("DB__HOST", "override")
        assert Settings().db.host == "override"


def test_aws_parameter_typo_in_sub_model_fails(monkeypatch, test_env):
    with mock_aws():
        boto3.client("ssm").put_parameter(
            Name="/shop/prd/db/pool_szie", Value="1", Type="String"
        )
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")
        with pytest.raises(ValidationError, match="pool_szie"):
            Settings()


def test_aws_parameter_typo_in_top_level_segment_is_ignored(
    monkeypatch, test_env
):
    with mock_aws():
        ssm = boto3.client("ssm")
        ssm.put_parameter(
            Name="/shop/prd/corss/allow_origins",
            Value='["https://x.test"]',
            Type="String",
        )
        ssm.put_parameter(
            Name="/shop/prd/Db/host", Value="wrong-case", Type="String"
        )
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")
        settings = Settings()
        assert settings.cors.allow_origins == []
        assert settings.db.host == "localhost"


def test_defaults_mode_shortens_source_timeouts(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULTS_MODE", "in-region")
    config = boto3.client("ssm").meta.config
    assert config.connect_timeout == 1.1
    assert config.retries["mode"] == "standard"

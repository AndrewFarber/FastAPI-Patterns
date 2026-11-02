import json

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError

from app.core.config.db import PasswordAuth
from app.core.config.settings import Settings


def test_aws_sources_merge_secret_and_parameters(monkeypatch):
    with mock_aws():
        boto3.client("secretsmanager").create_secret(Name="shop/prd/app", SecretString=json.dumps({"db--auth--password": "p@ss"}))
        ssm = boto3.client("ssm")
        for name, value in {
            "/shop/prd/db/host": "rds",
            "/shop/prd/db/user": "shop_app",
            "/shop/prd/db/name": "shop",
            "/shop/prd/db/sslmode": "disable",
            "/shop/prd/db/auth/method": "password",
            "/shop/prd/events/topic_arn": "arn:aws:sns:us-east-1:123456789012:shop-events",
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
        boto3.client("ssm").put_parameter(Name="/shop/prd/db/pool_szie", Value="1", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")
        with pytest.raises(ValidationError, match="pool_szie"):
            Settings()


def test_aws_parameter_typo_in_top_level_segment_is_ignored(monkeypatch, test_env):
    with mock_aws():
        ssm = boto3.client("ssm")
        ssm.put_parameter(Name="/shop/prd/corss/allow_origins", Value='["https://x.test"]', Type="String")
        ssm.put_parameter(Name="/shop/prd/Db/host", Value="wrong-case", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")
        settings = Settings()
        assert settings.cors.allow_origins == []
        assert settings.db.host == "localhost"


def test_defaults_mode_shortens_source_timeouts(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULTS_MODE", "in-region")
    config = boto3.client("ssm").meta.config
    assert config.connect_timeout == 1.1
    assert config.retries["mode"] == "standard"

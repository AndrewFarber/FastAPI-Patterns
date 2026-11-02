import json
import os

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError
from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AWSSystemsManagerSettingsSource,
)

from app.core.config.db import PasswordAuth
from app.core.config.settings import Settings


class AwsSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        sources = [init_settings, env_settings]
        if secret_id := os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID"):
            sources.append(AWSSecretsManagerSettingsSource(settings_cls, secret_id))
        if ssm_path := os.environ.get("AWS_SSM_PATH"):
            sources.append(AWSSystemsManagerSettingsSource(settings_cls, ssm_path))
        return tuple(sources)


def test_aws_sources_merge_secret_and_parameters(monkeypatch):
    with mock_aws():
        boto3.client("secretsmanager").create_secret(
            Name="shop/prd/app", SecretString=json.dumps({"db--auth--password": "p@ss"})
        )
        ssm = boto3.client("ssm")
        for name, value in {
            "/shop/prd/db/host": "rds", "/shop/prd/db/user": "shop_app", "/shop/prd/db/name": "shop",
            "/shop/prd/db/sslmode": "disable", "/shop/prd/db/auth/method": "password",
            "/shop/prd/auth/issuer": "https://issuer.test", "/shop/prd/auth/audiences": '["c1"]',
        }.items():
            ssm.put_parameter(Name=name, Value=value, Type="String")
        monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "shop/prd/app")
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")

        settings = AwsSettings()
        assert isinstance(settings.db.auth, PasswordAuth)
        assert settings.db.auth.password.get_secret_value() == "p@ss"
        assert settings.auth.audiences == ["c1"]

        monkeypatch.setenv("DB__HOST", "override")
        assert AwsSettings().db.host == "override"


def test_aws_parameter_typo_in_sub_model_fails(monkeypatch, test_env):
    with mock_aws():
        boto3.client("ssm").put_parameter(Name="/shop/prd/db/pool_szie", Value="1", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")
        with pytest.raises(ValidationError, match="pool_szie"):
            AwsSettings()


def test_aws_parameter_typo_in_top_level_segment_is_ignored(monkeypatch, test_env):
    with mock_aws():
        ssm = boto3.client("ssm")
        ssm.put_parameter(Name="/shop/prd/corss/allow_origins", Value='["https://x.test"]', Type="String")
        ssm.put_parameter(Name="/shop/prd/Db/host", Value="wrong-case", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/shop/prd")
        settings = AwsSettings()
        assert settings.cors.allow_origins == []
        assert settings.db.host == "localhost"


def test_defaults_mode_shortens_source_timeouts(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULTS_MODE", "in-region")
    config = boto3.client("ssm").meta.config
    assert config.connect_timeout == 1.1
    assert config.retries["mode"] == "standard"

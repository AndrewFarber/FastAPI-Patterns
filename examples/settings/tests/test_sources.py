"""Variants of the root Settings class shown in 3b-settings-aws-sources."""
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

from app.clients import aws_values
from app.config.db import PasswordAuth
from app.config.settings import Settings


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
            Name="orders/prd/app", SecretString=json.dumps({"db--auth--password": "p@ss"})
        )
        ssm = boto3.client("ssm")
        for name, value in {
            "/orders/prd/db/host": "rds", "/orders/prd/db/user": "orders_app", "/orders/prd/db/name": "orders",
            "/orders/prd/db/sslmode": "disable", "/orders/prd/db/auth/method": "password",
            "/orders/prd/auth/issuer": "https://issuer.test", "/orders/prd/auth/audiences": '["c1"]',
        }.items():
            ssm.put_parameter(Name=name, Value=value, Type="String")
        monkeypatch.setenv("AWS_SECRETS_MANAGER_SECRET_ID", "orders/prd/app")
        monkeypatch.setenv("AWS_SSM_PATH", "/orders/prd")

        settings = AwsSettings()
        assert isinstance(settings.db.auth, PasswordAuth)
        assert settings.db.auth.password.get_secret_value() == "p@ss"
        assert settings.auth.audiences == ["c1"]

        monkeypatch.setenv("DB__HOST", "override")
        assert AwsSettings().db.host == "override"          # env vars win over AWS


def test_aws_parameter_typo_in_sub_model_fails(monkeypatch, test_env):
    with mock_aws():
        boto3.client("ssm").put_parameter(Name="/orders/prd/db/pool_szie", Value="1", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/orders/prd")
        with pytest.raises(ValidationError, match="pool_szie"):
            AwsSettings()


def test_aws_parameter_typo_in_top_level_segment_is_ignored(monkeypatch, test_env):
    with mock_aws():
        ssm = boto3.client("ssm")
        ssm.put_parameter(Name="/orders/prd/corss/allow_origins", Value='["https://x.test"]', Type="String")
        ssm.put_parameter(Name="/orders/prd/Db/host", Value="wrong-case", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/orders/prd")
        settings = AwsSettings()
        assert settings.cors.allow_origins == []            # silently not configured
        assert settings.db.host == "localhost"


def test_defaults_mode_shortens_source_timeouts(monkeypatch):
    """The pydantic-settings sources build their own clients; AWS_DEFAULTS_MODE reaches them."""
    monkeypatch.setenv("AWS_DEFAULTS_MODE", "in-region")
    config = boto3.client("ssm").meta.config
    assert config.connect_timeout == 1.1
    assert config.retries["mode"] == "standard"


def test_value_cache_clients_have_short_timeouts(monkeypatch):
    created = []
    monkeypatch.setattr(aws_values.boto3, "client", lambda *args, **kwargs: created.append(kwargs["config"]))
    aws_values.secrets_manager_cache("us-east-1", 60)
    aws_values.parameter_store_cache("us-east-1", 60)
    for config in created:
        assert (config.connect_timeout, config.read_timeout) == (1, 2)
        assert config.retries["mode"] == "standard"
        # botocore rewrites max_attempts=2 (retries) to total_max_attempts=3 (calls) in place once a client is built
        assert config.retries.get("total_max_attempts", config.retries.get("max_attempts", 0) + 1) == 3

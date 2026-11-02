"""Variants of the root Settings class shown in 3a-settings-secret-files and 3b-settings-aws-sources-pydantic."""
import json
import os

import boto3
import pytest
from moto import mock_aws
from pydantic import ValidationError
from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AWSSystemsManagerSettingsSource,
    NestedSecretsSettingsSource,
)
from pydantic_settings.exceptions import SettingsError

from app.clients import aws_values
from app.config.db import PasswordAuth
from app.config.settings import Settings


class FileSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        sources = [init_settings, env_settings]
        if secrets_dir := os.environ.get("SECRETS_DIR"):
            sources.append(
                NestedSecretsSettingsSource(file_secret_settings, secrets_dir=secrets_dir, secrets_dir_missing="error")
            )
        return tuple(sources)


@pytest.fixture
def password_file(tmp_path, test_env, monkeypatch):
    (tmp_path / "db__auth__password").write_text("from-file")
    monkeypatch.delenv("DB__AUTH")
    monkeypatch.setenv("DB__AUTH__METHOD", "password")
    return tmp_path


def test_nested_secret_files(password_file, monkeypatch):
    monkeypatch.setenv("SECRETS_DIR", str(password_file))
    assert FileSettings().db.auth.password.get_secret_value() == "from-file"

    monkeypatch.setenv("DB__AUTH__PASSWORD", "from-env")
    assert FileSettings().db.auth.password.get_secret_value() == "from-env"   # env vars win over files


def test_secret_files_ignored_without_secrets_dir(password_file, monkeypatch):
    monkeypatch.delenv("SECRETS_DIR", raising=False)                          # as on Lambda
    with pytest.raises(ValidationError, match="password"):
        FileSettings()


def test_missing_secrets_dir_fails(test_env, monkeypatch):
    monkeypatch.setenv("SECRETS_DIR", "/run/secrets-that-do-not-exist")
    with pytest.raises(SettingsError, match="does not exist"):
        FileSettings()


class AwsSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        sources = [init_settings, env_settings, file_secret_settings]
        if secret_id := os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID"):
            sources.append(AWSSecretsManagerSettingsSource(settings_cls, secret_id))
        if ssm_path := os.environ.get("AWS_SSM_PATH"):
            sources.append(AWSSystemsManagerSettingsSource(settings_cls, ssm_path))
        return tuple(sources)


def test_aws_sources_merge_secret_and_parameters(aws_credentials, monkeypatch):
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


def test_aws_parameter_typo_in_sub_model_fails(aws_credentials, monkeypatch, test_env):
    with mock_aws():
        boto3.client("ssm").put_parameter(Name="/orders/prd/db/pool_szie", Value="1", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/orders/prd")
        with pytest.raises(ValidationError, match="pool_szie"):
            AwsSettings()


def test_aws_parameter_typo_in_top_level_segment_is_ignored(aws_credentials, monkeypatch, test_env):
    with mock_aws():
        ssm = boto3.client("ssm")
        ssm.put_parameter(Name="/orders/prd/emial/host", Value="smtp.test", Type="String")
        ssm.put_parameter(Name="/orders/prd/Db/host", Value="wrong-case", Type="String")
        monkeypatch.setenv("AWS_SSM_PATH", "/orders/prd")
        settings = AwsSettings()
        assert settings.email is None                       # silently not configured
        assert settings.db.host == "localhost"


def test_defaults_mode_shortens_source_timeouts(aws_credentials, monkeypatch):
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

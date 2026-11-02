import logging

import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_settings import AWSSystemsManagerSettingsSource, BaseSettings, SettingsConfigDict

from app.config.app import AppSettings
from app.observability import DeploymentFilter


def settings_with(db_model):
    class S(BaseSettings):
        model_config = SettingsConfigDict(env_nested_delimiter="__", extra="forbid", frozen=True)
        db: db_model

        @classmethod
        def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
            return (init_settings, env_settings, AWSSystemsManagerSettingsSource(settings_cls, "/orders/prd"))

    return S


class DbOld(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    host: str


class DbNew(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    host: str
    statement_timeout_ms: int = 30000      # expand: declared with a default


def test_expand_then_contract(aws_credentials):
    with mock_aws():
        ssm = boto3.client("ssm")
        ssm.put_parameter(Name="/orders/prd/db/host", Value="h", Type="String")
        assert settings_with(DbNew)().db.statement_timeout_ms == 30000    # new version works without the value
        assert settings_with(DbOld)().db.host == "h"                      # old version unaffected
        ssm.put_parameter(Name="/orders/prd/db/statement_timeout_ms", Value="5000", Type="String")
        with pytest.raises(ValidationError, match="statement_timeout_ms"):
            settings_with(DbOld)()                                        # too early: old version can't start
        assert settings_with(DbNew)().db.statement_timeout_ms == 5000

        # Contract: delete the value while the running version still declares the field...
        ssm.delete_parameter(Name="/orders/prd/db/statement_timeout_ms")
        assert settings_with(DbNew)().db.statement_timeout_ms == 30000
        assert settings_with(DbOld)().db.host == "h"                      # ...then a release can drop the field


def make_record() -> logging.LogRecord:
    return logging.LogRecord("app.orders", logging.INFO, __file__, 1, "hello", None, None)


def test_deployment_filter_tags_lambda_function_version(monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_VERSION", "7")             # set by Lambda in each environment
    record = make_record()
    assert DeploymentFilter(AppSettings(version="1.4.2")).filter(record)
    assert (record.version, record.function_version) == ("1.4.2", "7")


def test_deployment_filter_off_lambda(monkeypatch):
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_VERSION", raising=False)
    record = make_record()
    DeploymentFilter(AppSettings()).filter(record)
    assert (record.version, record.function_version) == (None, None)

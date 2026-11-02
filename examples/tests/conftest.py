import json
import logging
import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from app.core.config.settings import Settings, get_settings
from app.core.db.base import Base
from app.services.orders.infrastructure.models import OrderRow
from app.services.users.infrastructure.models import UserRow

TEST_VALUES: dict[str, dict[str, Any]] = {
    "db": {
        "host": "localhost", "user": "test", "name": "shop_test", "sslmode": "disable",
        "auth": {"method": "password", "password": "test"},
    },
    "auth": {"issuer": "https://issuer.test", "audiences": ["test-client"]},
}


def make_test_settings() -> Settings:
    return Settings(**TEST_VALUES)


def make_test_env() -> dict[str, str]:
    return {
        f"{section}__{key}".upper(): json.dumps(value) if isinstance(value, (list, dict)) else str(value)
        for section, fields in TEST_VALUES.items()
        for key, value in fields.items()
    }


def clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    sections = {name.upper() for name in Settings.model_fields}
    source_switches = {"AWS_SECRETS_MANAGER_SECRET_ID", "AWS_SSM_PATH"}
    for key in list(os.environ):
        upper = key.upper()
        if upper.split("__")[0] in sections or upper in source_switches:
            monkeypatch.delenv(key)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_env(monkeypatch)


@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in make_test_env().items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def create_app(test_env) -> Iterator[Callable[[], FastAPI]]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    from app.main import create_app
    yield create_app
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def engine() -> Iterator[Engine]:
    tables = [UserRow.__table__, OrderRow.__table__]
    schemas = {table.schema: None for table in tables}
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    ).execution_options(schema_translate_map=schemas)
    Base.metadata.create_all(engine, tables=tables)
    yield engine
    engine.dispose()


@pytest.fixture
def client(create_app, engine, monkeypatch) -> Iterator[TestClient]:
    from app import main

    monkeypatch.setattr(main, "build_engine", lambda db, application_name: engine)
    with TestClient(create_app()) as client:
        yield client

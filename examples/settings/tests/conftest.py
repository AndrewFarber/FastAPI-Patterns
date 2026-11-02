import json
import logging
import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI

from app.config.settings import Settings, get_settings

# One source of truth for test configuration
TEST_VALUES: dict[str, dict[str, Any]] = {
    "db": {
        "host": "localhost", "user": "test", "name": "orders_test", "sslmode": "disable",
        "auth": {"method": "password", "password": "test"},
    },
    "auth": {"issuer": "https://issuer.test", "audiences": ["test-client"]},
}


def make_test_settings() -> Settings:   # not test_*: pytest would collect it as a test
    return Settings(**TEST_VALUES)


def make_test_env() -> dict[str, str]:
    """TEST_VALUES as env vars: DB__HOST=localhost, lists and dicts as JSON."""
    return {
        f"{section}__{key}".upper(): json.dumps(value) if isinstance(value, (list, dict)) else str(value)
        for section, fields in TEST_VALUES.items()
        for key, value in fields.items()
    }


def clear_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the developer's own APP__*, DB__*, ... so APP__IS_PRD=true in a shell can't change a test."""
    sections = {name.upper() for name in Settings.model_fields}
    aws_sources = {"AWS_SECRETS_MANAGER_SECRET_ID", "AWS_SSM_PATH"}
    for key in list(os.environ):
        upper = key.upper()                          # env var names are matched case-insensitively
        if upper.split("__")[0] in sections or upper in aws_sources:
            monkeypatch.delenv(key)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_settings_env(monkeypatch)


# Set the environment, not dependency_overrides.
# Overrides only reach request-time Depends(); startup code that calls
# get_settings() directly would still read the real environment.
@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for key, value in make_test_env().items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()          # rebuild from the test environment
    yield
    get_settings.cache_clear()          # don't leak test settings into other tests


@pytest.fixture
def create_app(test_env) -> Iterator[Callable[[], FastAPI]]:
    """app.main.create_app, imported after test_env: importing app.main builds its module-level app."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    from app.main import create_app
    yield create_app
    root.handlers[:] = handlers         # create_app() configured the root logger
    root.setLevel(level)


@pytest.fixture
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake credentials for moto and for signing IAM tokens offline."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

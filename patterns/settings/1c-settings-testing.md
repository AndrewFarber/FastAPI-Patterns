---
title: "Testing settings"
category: testing
tags: [settings, pytest, fixtures]
status: draft
related: ["[[1a-settings-management]]", "[[1b-settings-access]]"]
---

# Testing settings

## Problem
Tests need a complete, valid `Settings` without real secrets, and without a developer's own environment leaking in. Each access approach in [[1b-settings-access]] needs a different way to substitute it.

## Use when
- Any test suite for an app that uses `Settings`.

## Avoid when
- Never.

## Solution
```python
# tests/conftest.py
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
```

- **`clean_env`** runs for every test and removes the developer's own `APP__*`, `DB__*`, ... variables (one prefix per top-level field of `Settings`), so `APP__IS_PRD=true` left in a shell can't switch on prod-only validation in a test.
- **`create_app`** hands a test the factory from `app.main`, imported only after `test_env`: importing `app.main` builds its module-level `app`, which needs a valid environment. Tests that need other values set them with `monkeypatch.setenv`, call `get_settings.cache_clear()`, then `create_app()`. The fixture restores the root logger that `create_app()` configured.
- **Approach 3** (app factory) needs none of this: tests pass settings in, `create_app(make_test_settings())`.
- **Approach 1** (module singleton) reads the environment at import time, so variables must be set before `app.config.settings` is first imported (e.g. at the top of `conftest.py`).
- **Sub-models test on their own:** `FeatureSettings(new_checkout=True)`, `CorsSettings(allow_origins=[...])`. No root `Settings` needed.
- **AWS sources** stay off in tests because `clean_env` removes `AWS_SECRETS_MANAGER_SECRET_ID` and `AWS_SSM_PATH`; see [[3b-settings-aws-sources-pydantic]] for testing them with `moto`.
- **`aws_credentials`** sets fake AWS credentials for tests that use `moto` or sign IAM tokens offline, so no test can reach a real AWS account.

## Pitfalls
- **Partial overrides.** Init kwargs override env vars, but fields not passed still fall back to the environment. `clean_env` empties it of settings variables; still pass every value a test depends on.
- **Importing `app.main` at the top of `conftest.py`.** Its module-level `create_app()` runs at collection time, before any fixture has set the environment.
- **Helper names starting with `test_`.** pytest collects them as tests.
- **Forgetting `cache_clear()`.** With approach 2, the first test's settings stay cached for the whole session.

## Related
- [[1a-settings-management]]
- [[1b-settings-access]]

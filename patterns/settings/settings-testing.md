---
title: "Testing settings"
category: testing
related:
  - "[[settings-guide]]"
  - "[[settings-aws-sources]]"
  - "[[services-events]]"
  - "[[settings-access]]"
---

# Testing settings

## Overview
Tests build settings from one dict of test values, through the environment rather than `dependency_overrides`, after clearing the developer's own settings variables. Every test gets a complete, valid `Settings` that no shell variable can change.

## Rules
- **Set the environment, not overrides,** so startup code that calls `get_settings()` directly sees test values.
- **`cache_clear()` before and after** each test that changes the environment.
- **Pass every value a test depends on;** fields not passed fall back to the (cleaned) environment.
- **AWS stays offline:** `aws_credentials` (autouse) drops the developer's `AWS_PROFILE` and sets fake keys in every test; AWS wiring is tested with `moto` ([[settings-aws-sources]]).

## Code example
```python
# tests/conftest.py
import json
import logging
import os
from collections.abc import Callable, Iterator
from typing import Any

import boto3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws
from sqlalchemy import Engine, create_engine
from sqlalchemy.pool import StaticPool

from app.core.config.settings import Settings, get_settings
from app.core.db.base import Base
from app.core.events.consumer import EventConsumer
from app.core.events.models import ProcessedEventRow
from app.core.outbox.models import OutboxRow
from app.core.outbox.relay import OutboxRelay
from app.services.orders.infrastructure.models import OrderRow
from app.services.users.infrastructure.models import UserRow

TEST_VALUES: dict[str, dict[str, Any]] = {
    "db": {
        "host": "localhost",
        "user": "test",
        "name": "shop_test",
        "sslmode": "disable",
        "auth": {"method": "password", "password": "test"},
    },
    "events": {"topic_arn": "arn:aws:sns:us-east-1:123456789012:shop-events"},
    "switches": {"region": "us-east-1", "orders_paused": "/shop/switches/orders-paused"},
}


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
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture
def create_app(test_env, restore_logging) -> Callable[[], FastAPI]:
    from app.main import create_app

    return create_app


@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("AWS_PROFILE", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


@pytest.fixture
def engine() -> Iterator[Engine]:
    tables = [UserRow.__table__, OrderRow.__table__, OutboxRow.__table__, ProcessedEventRow.__table__]
    schemas = {table.schema: None for table in tables}
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}).execution_options(
        schema_translate_map=schemas
    )
    Base.metadata.create_all(engine, tables=tables)
    yield engine
    engine.dispose()


class RecordingSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, event_type: str, body: str) -> None:
        self.sent.append((event_type, body))


@pytest.fixture
def sender() -> RecordingSender:
    return RecordingSender()


@pytest.fixture
def relay(engine, sender) -> OutboxRelay:
    return OutboxRelay(engine, sender)


@pytest.fixture
def aws() -> Iterator[str]:
    with mock_aws():
        boto3.client("ssm").put_parameter(Name=TEST_VALUES["switches"]["orders_paused"], Value="false", Type="String")
        yield boto3.client("sns").create_topic(Name="shop-events")["TopicArn"]


@pytest.fixture
def workers(test_env, restore_logging, aws, engine, monkeypatch):
    from app import workers

    monkeypatch.setattr(workers, "build_engine", lambda db, application_name: engine)
    return workers.create_workers()


def subscribe_queue(topic_arn: str, consumer: EventConsumer) -> str:
    sqs = boto3.client("sqs")
    queue_url = sqs.create_queue(QueueName=f"shop-{consumer.name}-events")["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
    boto3.client("sns").subscribe(
        TopicArn=topic_arn,
        Protocol="sqs",
        Endpoint=queue_arn,
        Attributes={"RawMessageDelivery": "true", "FilterPolicy": json.dumps({"event_type": consumer.event_names})},
    )
    return queue_url


def deliver(queue_url: str, consumer: EventConsumer) -> dict[str, list[dict[str, str]]]:
    sqs = boto3.client("sqs")
    messages = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10).get("Messages", [])
    result = consumer.handle({"Records": [{"messageId": m["MessageId"], "body": m["Body"]} for m in messages]})
    failed = {failure["itemIdentifier"] for failure in result["batchItemFailures"]}
    for m in messages:
        if m["MessageId"] not in failed:
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=m["ReceiptHandle"])
    return result


@pytest.fixture
def client(create_app, aws, engine, monkeypatch) -> Iterator[TestClient]:
    from app import main

    monkeypatch.setattr(main, "build_engine", lambda db, application_name: engine)
    with TestClient(create_app()) as client:
        yield client
```

- **`TEST_VALUES`** is the one source of test configuration; `make_test_env()` turns it into env vars.
- **`clean_env`** (autouse) removes every env var whose prefix is a top-level `Settings` field, plus the AWS source switches, so `APP__IS_PRD=true` in a shell can't change a test.
- **`create_app`** imports `app.main` only after `test_env`, because importing it builds the module-level app. Tests needing other values `monkeypatch.setenv`, `get_settings.cache_clear()`, then call it.
- **`aws`** starts `moto` and creates the SNS topic and the `orders_paused` parameter (`"false"`) from `TEST_VALUES`, so the lifespan finds it; **`workers`** builds the event consumers on the test engine, and `subscribe_queue()` / `deliver()` run the SQS hop ([[services-events]]).
- **Sub-models test on their own:** `FeatureSettings(new_checkout=True)`, no root `Settings` needed. Code below the entry points takes sub-models ([[settings-access]]), so its tests never touch the environment.

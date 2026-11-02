from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events.consumer import EventConsumer
from app.core.events.messages import encode, event_name, to_payload
from app.core.events.models import ProcessedEventRow
from app.core.outbox.models import OutboxRow
from app.services.users import UserDeactivated


def record(event, message_id="m1") -> dict:
    return {
        "messageId": message_id,
        "body": encode(event_name(type(event)), to_payload(event)),
    }


@pytest.fixture
def consumer(engine, relay) -> EventConsumer:
    return EventConsumer("orders", engine, relay)


def test_handles_each_event_once(consumer):
    seen = []
    consumer.subscribe(
        UserDeactivated, lambda event, uow: seen.append(event.user_id)
    )
    event = UserDeactivated(user_id=1)
    assert consumer.handle(
        {"Records": [record(event, "m1"), record(event, "m2")]}
    ) == {"batchItemFailures": []}
    assert seen == [1]


def test_failing_handler_reports_the_message_and_can_retry(consumer):
    calls = []

    def flaky(event, uow):
        calls.append(event.user_id)
        if len(calls) == 1:
            raise RuntimeError("handler bug")

    consumer.subscribe(UserDeactivated, flaky)
    event = UserDeactivated(user_id=1)
    assert consumer.handle({"Records": [record(event)]}) == {
        "batchItemFailures": [{"itemIdentifier": "m1"}]
    }
    assert consumer.handle({"Records": [record(event)]}) == {
        "batchItemFailures": []
    }
    assert calls == [1, 1]


def test_handlers_publish_through_their_own_outbox(consumer, engine, sender):
    consumer.subscribe(
        UserDeactivated,
        lambda event, uow: uow.events.publish(UserDeactivated(user_id=2)),
    )
    consumer.handle({"Records": [record(UserDeactivated(user_id=1))]})
    with Session(engine) as session:
        assert [
            row.payload["user_id"] for row in session.scalars(select(OutboxRow))
        ] == [2]
    assert len(sender.sent) == 1


def test_unsubscribed_event_is_acknowledged(consumer):
    assert consumer.handle(
        {"Records": [record(UserDeactivated(user_id=1))]}
    ) == {"batchItemFailures": []}


def test_purge_deletes_only_this_consumers_old_records(consumer, engine, relay):
    consumer.subscribe(UserDeactivated, lambda event, uow: None)
    other = EventConsumer("billing", engine, relay)
    other.subscribe(UserDeactivated, lambda event, uow: None)
    event = UserDeactivated(user_id=1)
    consumer.handle({"Records": [record(event)]})
    other.handle({"Records": [record(event)]})

    assert consumer.purge(datetime.now(UTC) - timedelta(days=1)) == 0
    assert consumer.purge(datetime.now(UTC) + timedelta(seconds=1)) == 1
    with Session(engine) as session:
        assert [
            row.consumer for row in session.scalars(select(ProcessedEventRow))
        ] == ["billing"]

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events.consumer import EventConsumer
from app.core.events.messages import encode, get_event_name, to_payload
from app.core.events.models import DbProcessedEvent
from app.core.outbox.models import DbOutboxEvent
from app.services.users import UserDeactivated


def create_record(event, message_id="m1") -> dict:
    return {
        "messageId": message_id,
        "body": encode(get_event_name(type(event)), to_payload(event)),
    }


@pytest.fixture
def consumer(engine, relay) -> EventConsumer:
    return EventConsumer("orders", engine, relay)


def test_handles_each_event_once(consumer):
    seen = []
    consumer.subscribe(
        UserDeactivated, lambda event, unit_of_work: seen.append(event.user_id)
    )
    event = UserDeactivated(user_id=1)
    assert consumer.handle(
        {"Records": [create_record(event, "m1"), create_record(event, "m2")]}
    ) == {"batchItemFailures": []}
    assert seen == [1]


def test_failing_handler_reports_the_message_and_can_retry(consumer):
    calls = []

    def flaky(event, unit_of_work):
        calls.append(event.user_id)
        if len(calls) == 1:
            raise RuntimeError("handler bug")

    consumer.subscribe(UserDeactivated, flaky)
    event = UserDeactivated(user_id=1)
    assert consumer.handle({"Records": [create_record(event)]}) == {
        "batchItemFailures": [{"itemIdentifier": "m1"}]
    }
    assert consumer.handle({"Records": [create_record(event)]}) == {
        "batchItemFailures": []
    }
    assert calls == [1, 1]


def test_handlers_publish_through_their_own_outbox(
    consumer, engine, message_sender
):
    consumer.subscribe(
        UserDeactivated,
        lambda event, unit_of_work: unit_of_work.event_publisher.publish(
            UserDeactivated(user_id=2)
        ),
    )
    consumer.handle({"Records": [create_record(UserDeactivated(user_id=1))]})
    with Session(engine) as session:
        assert [
            db_outbox_event.payload["user_id"]
            for db_outbox_event in session.scalars(select(DbOutboxEvent))
        ] == [2]
    assert len(message_sender.sent) == 1


def test_unsubscribed_event_is_acknowledged(consumer):
    assert consumer.handle(
        {"Records": [create_record(UserDeactivated(user_id=1))]}
    ) == {"batchItemFailures": []}


def test_purge_deletes_only_this_consumers_old_records(consumer, engine, relay):
    consumer.subscribe(UserDeactivated, lambda event, unit_of_work: None)
    other = EventConsumer("billing", engine, relay)
    other.subscribe(UserDeactivated, lambda event, unit_of_work: None)
    event = UserDeactivated(user_id=1)
    consumer.handle({"Records": [create_record(event)]})
    other.handle({"Records": [create_record(event)]})

    assert consumer.purge(datetime.now(UTC) - timedelta(days=1)) == 0
    assert consumer.purge(datetime.now(UTC) + timedelta(seconds=1)) == 1
    with Session(engine) as session:
        assert [
            db_processed_event.consumer
            for db_processed_event in session.scalars(select(DbProcessedEvent))
        ] == ["billing"]

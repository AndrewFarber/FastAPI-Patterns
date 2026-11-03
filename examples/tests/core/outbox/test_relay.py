import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db.unit_of_work import UnitOfWork
from app.core.outbox.models import DbOutboxEvent
from app.core.outbox.publisher import OutboxEventPublisher
from app.core.outbox.relay import CHUNK_SIZE, OutboxRelay
from app.services.users import UserDeactivated


def get_db_outbox_events(engine) -> list[DbOutboxEvent]:
    with Session(engine) as session:
        return list(session.scalars(select(DbOutboxEvent)))


def test_event_is_stored_with_the_change_and_sent_after_commit(
    engine, relay, message_sender
):
    with UnitOfWork(engine, relay) as unit_of_work:
        unit_of_work.event_publisher.publish(UserDeactivated(user_id=1))
        assert message_sender.sent == []
    [(event_type, body)] = message_sender.sent
    assert event_type == "UserDeactivated"
    assert json.loads(body)["payload"]["user_id"] == 1
    [db_outbox_event] = get_db_outbox_events(engine)
    assert db_outbox_event.sent_at is not None


def test_rollback_stores_and_sends_nothing(engine, relay, message_sender):
    with pytest.raises(RuntimeError), UnitOfWork(engine, relay) as unit_of_work:
        unit_of_work.event_publisher.publish(UserDeactivated(user_id=1))
        raise RuntimeError("use case failed")
    assert get_db_outbox_events(engine) == [] and message_sender.sent == []


def test_failed_send_keeps_the_change_and_the_sweeper_sends_it(
    engine, relay, message_sender, monkeypatch
):
    def unreachable(event_type, body):
        raise ConnectionError("SNS unreachable")

    monkeypatch.setattr(message_sender, "send", unreachable)
    with UnitOfWork(engine, relay) as unit_of_work:
        unit_of_work.session.execute(
            text(
                "INSERT INTO users (name, status, version) "
                "VALUES ('ann', 'deactivated', 1)"
            )
        )
        unit_of_work.event_publisher.publish(UserDeactivated(user_id=1))
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM users")) == 1
    assert get_db_outbox_events(engine)[0].sent_at is None

    monkeypatch.undo()
    assert relay.sweep() == 1
    assert (
        len(message_sender.sent) == 1
        and get_db_outbox_events(engine)[0].sent_at is not None
    )
    assert relay.sweep() == 0


def test_one_failing_event_doesnt_hold_back_the_others(
    engine, relay, message_sender, monkeypatch
):
    poison = UserDeactivated(user_id=1)
    send = message_sender.send

    def fail_poison(event_type, body):
        if json.loads(body)["payload"]["event_id"] == str(poison.event_id):
            raise ValueError("message too large")
        send(event_type, body)

    monkeypatch.setattr(message_sender, "send", fail_poison)
    with UnitOfWork(engine, relay) as unit_of_work:
        unit_of_work.event_publisher.publish(poison)
        unit_of_work.event_publisher.publish(UserDeactivated(user_id=2))
    assert [
        json.loads(body)["payload"]["user_id"]
        for _, body in message_sender.sent
    ] == [2]
    assert relay.sweep() == 0
    assert [
        db_outbox_event.event_id
        for db_outbox_event in get_db_outbox_events(engine)
        if db_outbox_event.sent_at is None
    ] == [poison.event_id]


def store_events(engine, count: int) -> list[UserDeactivated]:
    events = [UserDeactivated(user_id=n) for n in range(count)]
    with Session(engine) as session, session.begin():
        event_publisher = OutboxEventPublisher(session)
        for event in events:
            event_publisher.publish(event)
    return events


def test_rows_that_keep_failing_dont_block_newer_ones(
    engine, message_sender, monkeypatch
):
    poison = store_events(engine, 2)
    [fresh] = store_events(engine, 1)
    poison_ids = {str(event.event_id) for event in poison}

    def fail_poison(event_type, body):
        if json.loads(body)["payload"]["event_id"] in poison_ids:
            raise ValueError("message too large")
        message_sender.sent.append((event_type, body))

    monkeypatch.setattr(message_sender, "send", fail_poison)
    relay = OutboxRelay(engine, message_sender, batch_size=2)
    assert relay.sweep() == 0
    assert relay.sweep() == 1
    [(_, body)] = message_sender.sent
    assert json.loads(body)["payload"]["event_id"] == str(fresh.event_id)


class LambdaTimeout(BaseException):
    pass


def test_a_timeout_rolls_back_only_the_chunk_in_flight(
    engine, message_sender, monkeypatch
):
    store_events(engine, CHUNK_SIZE * 2)

    def time_out_after_one_chunk(event_type, body):
        if len(message_sender.sent) == CHUNK_SIZE + 1:
            raise LambdaTimeout()
        message_sender.sent.append((event_type, body))

    monkeypatch.setattr(message_sender, "send", time_out_after_one_chunk)
    relay = OutboxRelay(engine, message_sender)
    with pytest.raises(LambdaTimeout):
        relay.sweep()
    sent = [e for e in get_db_outbox_events(engine) if e.sent_at is not None]
    assert len(sent) == CHUNK_SIZE


def test_purge_deletes_only_rows_sent_before_the_cutoff(
    engine, relay, message_sender, monkeypatch
):
    with UnitOfWork(engine, relay) as unit_of_work:
        unit_of_work.event_publisher.publish(UserDeactivated(user_id=1))

    def unreachable(event_type, body):
        raise ConnectionError("SNS unreachable")

    monkeypatch.setattr(message_sender, "send", unreachable)
    with UnitOfWork(engine, relay) as unit_of_work:
        unit_of_work.event_publisher.publish(UserDeactivated(user_id=2))

    assert relay.purge(datetime.now(UTC) - timedelta(days=1)) == 0
    assert relay.purge(datetime.now(UTC) + timedelta(seconds=1)) == 1
    [pending] = get_db_outbox_events(engine)
    assert pending.sent_at is None

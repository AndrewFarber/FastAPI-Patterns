import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db.unit_of_work import UnitOfWork
from app.core.outbox.models import DbOutboxEvent
from app.services.users import UserDeactivated


def get_outbox_rows(engine) -> list[DbOutboxEvent]:
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
    [row] = get_outbox_rows(engine)
    assert row.sent_at is not None


def test_rollback_stores_and_sends_nothing(engine, relay, message_sender):
    with pytest.raises(RuntimeError), UnitOfWork(engine, relay) as unit_of_work:
        unit_of_work.event_publisher.publish(UserDeactivated(user_id=1))
        raise RuntimeError("use case failed")
    assert get_outbox_rows(engine) == [] and message_sender.sent == []


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
    assert get_outbox_rows(engine)[0].sent_at is None

    monkeypatch.undo()
    assert relay.sweep() == 1
    assert (
        len(message_sender.sent) == 1
        and get_outbox_rows(engine)[0].sent_at is not None
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
        row.event_id for row in get_outbox_rows(engine) if row.sent_at is None
    ] == [poison.event_id]


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
    [pending] = get_outbox_rows(engine)
    assert pending.sent_at is None

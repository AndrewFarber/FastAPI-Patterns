import json

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db.unit_of_work import UnitOfWork
from app.core.outbox.models import OutboxRow
from app.services.users import UserDeactivated


def outbox(engine) -> list[OutboxRow]:
    with Session(engine) as session:
        return list(session.scalars(select(OutboxRow)))


def test_event_is_stored_with_the_change_and_sent_after_commit(engine, relay, sender):
    with UnitOfWork(engine, relay) as uow:
        uow.events.publish(UserDeactivated(user_id=1))
        assert sender.sent == []
    [(event_type, body)] = sender.sent
    assert event_type == "UserDeactivated"
    assert json.loads(body)["payload"]["user_id"] == 1
    [row] = outbox(engine)
    assert row.sent_at is not None


def test_rollback_stores_and_sends_nothing(engine, relay, sender):
    with pytest.raises(RuntimeError), UnitOfWork(engine, relay) as uow:
        uow.events.publish(UserDeactivated(user_id=1))
        raise RuntimeError("use case failed")
    assert outbox(engine) == [] and sender.sent == []


def test_failed_send_keeps_the_change_and_the_sweeper_sends_it(engine, relay, sender, monkeypatch):
    def unreachable(event_type, body):
        raise ConnectionError("SNS unreachable")

    monkeypatch.setattr(sender, "send", unreachable)
    with UnitOfWork(engine, relay) as uow:
        uow.session.execute(text("INSERT INTO users (name, status) VALUES ('ann', 'deactivated')"))
        uow.events.publish(UserDeactivated(user_id=1))
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM users")) == 1
    assert outbox(engine)[0].sent_at is None

    monkeypatch.undo()
    assert relay.sweep() == 1
    assert len(sender.sent) == 1 and outbox(engine)[0].sent_at is not None
    assert relay.sweep() == 0

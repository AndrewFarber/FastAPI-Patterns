import pytest
from sqlalchemy import text

from app.core.db.unit_of_work import UnitOfWork
from app.core.events.bus import EventBus
from app.services.users import UserDeactivated


def test_dispatches_only_after_commit(engine):
    bus, seen = EventBus(engine), []
    bus.subscribe(UserDeactivated, lambda event, session: seen.append(event.user_id))
    with UnitOfWork(engine, bus) as uow:
        uow.events.publish(UserDeactivated(user_id=1))
        assert seen == []
    assert seen == [1]


def test_rollback_dispatches_nothing(engine):
    bus, seen = EventBus(engine), []
    bus.subscribe(UserDeactivated, lambda event, session: seen.append(event))
    with pytest.raises(RuntimeError), UnitOfWork(engine, bus) as uow:
        uow.events.publish(UserDeactivated(user_id=1))
        raise RuntimeError("use case failed")
    assert seen == []


def test_failing_handler_keeps_the_publishers_change(engine):
    bus, seen = EventBus(engine), []

    def failing(event, session):
        raise RuntimeError("handler bug")

    bus.subscribe(UserDeactivated, failing)
    bus.subscribe(UserDeactivated, lambda event, session: seen.append(event.user_id))
    with UnitOfWork(engine, bus) as uow:
        uow.session.execute(text("INSERT INTO users (name, status) VALUES ('ann', 'deactivated')"))
        uow.events.publish(UserDeactivated(user_id=1))
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM users")) == 1
    assert seen == [1]

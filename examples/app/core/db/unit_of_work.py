from types import TracebackType
from typing import Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.events.bus import EventBus, RecordingPublisher


class UnitOfWork:
    def __init__(self, engine: Engine, bus: EventBus) -> None:
        self._engine = engine
        self._bus = bus

    def __enter__(self) -> Self:
        self.session = Session(self._engine)
        self.events = RecordingPublisher()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        with self.session:
            if exc_type is not None:
                self.session.rollback()
                return
            self.session.commit()
        self._bus.dispatch(self.events.events)

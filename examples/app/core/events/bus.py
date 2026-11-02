import logging
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.shared.events.base import DomainEvent

logger = logging.getLogger(__name__)

type Handler[E: DomainEvent] = Callable[[E, Session], None]


class EventBus:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    def subscribe[E: DomainEvent](self, event_type: type[E], handler: Handler[E]) -> None:
        self._handlers[event_type].append(handler)

    def dispatch(self, events: list[DomainEvent]) -> None:
        for event in events:
            for handler in self._handlers[type(event)]:
                try:
                    with Session(self._engine) as session, session.begin():
                        handler(event, session)
                except Exception:
                    logger.exception("%s failed for %r", handler.__qualname__, event)


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)

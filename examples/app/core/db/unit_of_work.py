from types import TracebackType
from typing import Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.outbox.publisher import OutboxEventPublisher
from app.core.outbox.relay import OutboxRelay


class UnitOfWork:
    def __init__(self, engine: Engine, relay: OutboxRelay) -> None:
        self._engine = engine
        self._relay = relay

    def __enter__(self) -> Self:
        self.session = Session(self._engine)
        self.event_publisher = OutboxEventPublisher(self.session)
        return self

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        with self.session:
            if error_type is not None:
                self.session.rollback()
                return
            self.session.commit()
        self._relay.relay(self.event_publisher.event_ids)

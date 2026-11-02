import logging
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import Engine, Select, delete, select
from sqlalchemy.orm import Session

from app.core.events.messages import encode
from app.core.outbox.models import OutboxRow

logger = logging.getLogger(__name__)


class MessageSender(Protocol):
    def send(self, event_type: str, body: str) -> None: ...


class OutboxRelay:
    def __init__(
        self, engine: Engine, sender: MessageSender, batch_size: int = 100
    ) -> None:
        self._engine = engine
        self._sender = sender
        self._batch_size = batch_size

    def relay(self, event_ids: list[UUID]) -> None:
        if not event_ids:
            return
        try:
            self._send(_pending().where(OutboxRow.event_id.in_(event_ids)))
        except Exception:
            logger.exception(
                "relay of %d events failed; the sweeper will send them",
                len(event_ids),
            )

    def sweep(self) -> int:
        return self._send(
            _pending().order_by(OutboxRow.created_at).limit(self._batch_size)
        )

    def purge(self, sent_before: datetime) -> int:
        with Session(self._engine) as session, session.begin():
            return session.execute(
                delete(OutboxRow).where(OutboxRow.sent_at < sent_before)
            ).rowcount

    def _send(self, query: Select[tuple[OutboxRow]]) -> int:
        sent = 0
        with Session(self._engine) as session, session.begin():
            for row in session.scalars(query).all():
                try:
                    self._sender.send(
                        row.event_type, encode(row.event_type, row.payload)
                    )
                except Exception:
                    logger.exception(
                        "sending event %s failed; the next sweep retries it",
                        row.event_id,
                    )
                    continue
                row.sent_at = datetime.now(UTC)
                sent += 1
        return sent


def _pending() -> Select[tuple[OutboxRow]]:
    # Locked rows belong to another relay or sweep, which will send them
    return (
        select(OutboxRow)
        .where(OutboxRow.sent_at.is_(None))
        .with_for_update(skip_locked=True)
    )

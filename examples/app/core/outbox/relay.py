import logging
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import Engine, Select, delete, select
from sqlalchemy.orm import Session

from app.core.events.messages import encode
from app.core.outbox.models import DbOutboxEvent

logger = logging.getLogger(__name__)

# Rows sent per transaction: a timeout rolls back only the rows in flight,
# and a slow send holds few locks
CHUNK_SIZE = 10


class MessageSender(Protocol):
    def send(self, event_type: str, body: str) -> None: ...


class OutboxRelay:
    def __init__(
        self,
        engine: Engine,
        message_sender: MessageSender,
        batch_size: int = 100,
    ) -> None:
        self._engine = engine
        self._message_sender = message_sender
        self._batch_size = batch_size

    def relay(self, event_ids: list[UUID]) -> None:
        if not event_ids:
            return
        try:
            for start in range(0, len(event_ids), CHUNK_SIZE):
                chunk = event_ids[start : start + CHUNK_SIZE]
                self._send(_pending().where(DbOutboxEvent.event_id.in_(chunk)))
        except Exception:
            logger.exception(
                "relay of %d events failed; the sweeper will send them",
                len(event_ids),
            )

    def sweep(self) -> int:
        sent, remaining = 0, self._batch_size
        while remaining > 0:
            limit = min(CHUNK_SIZE, remaining)
            selected, chunk_sent = self._send(
                _pending()
                # Rows that keep failing sink behind fresh ones
                .order_by(DbOutboxEvent.attempts, DbOutboxEvent.created_at)
                .limit(limit)
            )
            sent += chunk_sent
            remaining -= selected
            if selected < limit:
                break
        return sent

    def purge(self, sent_before: datetime) -> int:
        with Session(self._engine) as session, session.begin():
            return session.execute(
                delete(DbOutboxEvent).where(DbOutboxEvent.sent_at < sent_before)
            ).rowcount

    def _send(self, query: Select[tuple[DbOutboxEvent]]) -> tuple[int, int]:
        sent = 0
        with Session(self._engine) as session, session.begin():
            db_outbox_events = session.scalars(query).all()
            for db_outbox_event in db_outbox_events:
                try:
                    self._message_sender.send(
                        db_outbox_event.event_type,
                        encode(
                            db_outbox_event.event_type, db_outbox_event.payload
                        ),
                    )
                except Exception:
                    logger.exception(
                        "sending event %s failed; the next sweep retries it",
                        db_outbox_event.event_id,
                    )
                    db_outbox_event.attempts += 1
                    continue
                db_outbox_event.sent_at = datetime.now(UTC)
                sent += 1
        return len(db_outbox_events), sent


def _pending() -> Select[tuple[DbOutboxEvent]]:
    # Locked rows belong to another relay or sweep, which will send them
    return (
        select(DbOutboxEvent)
        .where(DbOutboxEvent.sent_at.is_(None))
        .with_for_update(skip_locked=True)
    )

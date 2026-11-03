from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.events.messages import get_event_name, to_payload
from app.core.outbox.models import DbOutboxEvent
from app.shared.events.base import DomainEvent


class OutboxEventPublisher:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.event_ids: list[UUID] = []

    def publish(self, event: DomainEvent) -> None:
        self._session.add(
            DbOutboxEvent(
                event_id=event.event_id,
                event_type=get_event_name(type(event)),
                payload=to_payload(event),
                created_at=datetime.now(UTC),
            )
        )
        self.event_ids.append(event.event_id)

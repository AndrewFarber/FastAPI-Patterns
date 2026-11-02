import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine

from app.core.db.unit_of_work import UnitOfWork
from app.core.events.messages import decode, event_name, from_payload
from app.core.events.models import ProcessedEventRow
from app.core.outbox.relay import OutboxRelay
from app.shared.events.base import DomainEvent

logger = logging.getLogger(__name__)

type Handler[E: DomainEvent] = Callable[[E, UnitOfWork], None]


class EventConsumer:
    def __init__(self, name: str, engine: Engine, relay: OutboxRelay) -> None:
        self.name = name
        self._engine = engine
        self._relay = relay
        self._types: dict[str, type[DomainEvent]] = {}
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(list)

    @property
    def event_names(self) -> list[str]:
        return sorted(self._types)

    def subscribe[E: DomainEvent](self, event_type: type[E], handler: Handler[E]) -> None:
        self._types[event_name(event_type)] = event_type
        self._handlers[event_type].append(handler)

    def handle(self, sqs_event: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
        failures = []
        for record in sqs_event["Records"]:
            try:
                self._handle(record["body"])
            except Exception:
                logger.exception("%s failed to handle message %s", self.name, record["messageId"])
                failures.append({"itemIdentifier": record["messageId"]})
        return {"batchItemFailures": failures}

    def _handle(self, body: str) -> None:
        name, payload = decode(body)
        event_type = self._types.get(name)
        if event_type is None:
            logger.warning("%s has no handler for %s; check the subscription's filter policy", self.name, name)
            return
        event = from_payload(event_type, payload)
        with UnitOfWork(self._engine, self._relay) as uow:
            if uow.session.get(ProcessedEventRow, (event.event_id, self.name)) is not None:
                return
            uow.session.add(ProcessedEventRow(event_id=event.event_id, consumer=self.name))
            for handler in self._handlers[event_type]:
                handler(event, uow)

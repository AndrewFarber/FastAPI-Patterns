---
title: "Services: events"
category: project-structure
related:
  - "[[services-guide]]"
---

# Services: events

## Overview
One service announces a fact, and other services react to it later in their own transaction. The event is stored in an outbox table in the publisher's transaction, sent to an SNS topic right after commit, and delivered to one SQS queue per subscribing service. The publisher owns the event and never knows who listens; each subscriber decides what the fact means for its own domain. No event is lost to a crash or an SNS outage, and a failing subscriber retries on its own without affecting the others.

## Rules
- **The publisher owns the event:** it lives in the publisher's `domain/events.py`, and subscribers import it only from the publisher's `__init__.py`.
- **Facts, in the past tense:** `UserDeactivated`, named in the publisher's terms; never an instruction to a subscriber.
- **Plain values only:** frozen dataclasses with IDs and the fields subscribers need, all JSON-serializable; never entities or ORM models.
- **The class name is the wire name,** unique across the app. Change an event by adding fields with defaults; a renamed class or a changed meaning is a new event.
- **Stored with the change:** the outbox row is written in the publisher's transaction; a rollback drops it.
- **Sent after commit, before the response:** the unit of work dependency uses `scope="function"`. A failed commit becomes a 5xx instead of a 2xx for a change that never happened, and nothing runs after the response, when Lambda may already have frozen the environment. The SNS client's short timeouts ([[settings-refreshing-values]]) cap what a slow SNS adds to the request.
- **The sweeper catches what the relay missed:** a crash between commit and send, or SNS being down. Alarm on the age of the oldest pending row.
- **Each row is locked while it's sent:** the relay and the sweeper both select pending rows `FOR UPDATE SKIP LOCKED`, so they never send the same row; a row another one holds is left for it.
- **One bad row doesn't block the rest:** each row is sent on its own; a row that fails stays pending and the next sweep retries it, while the rows after it go out. A row that never sends shows up in the oldest-pending alarm.
- **At least once:** a crash or failed commit after a send, and SNS and SQS themselves, can deliver twice. The consumer records `(event_id, consumer)` in `events.processed` in the handler's transaction and skips repeats.
- **No ordering:** standard topics and queues reorder messages; a handler that needs order checks the state it changes, not the order of events.
- **One queue per subscribing service,** with its own DLQ, so a failing service retries without delaying the others. Its filter policy lists `consumer.event_names`.
- **Handlers run in their own unit of work:** a failing handler doesn't undo the publisher's work, and an event a handler publishes goes through the outbox like any other.
- **Handlers hold no rules:** they call a use case of their own service, like `api/` does.
- **Purge old rows:** `purge_events` deletes sent outbox rows and processed records older than `events.retention_days` (30 by default), daily. Keep it longer than the longest retry window, DLQ retention and redrive included: a purged record lets a late redelivery run again.
- **The payload is `JSONB` on Postgres** (plain `JSON` elsewhere, for the SQLite tests), and a partial index on `created_at WHERE sent_at IS NULL` keeps the sweeper's query small however many sent rows are kept.
- **The worker image runs the Lambda runtime:** the `python` base image needs `awslambdaric` as its entry point and the handler as its command.
- **Tests:** the publisher's tests pass a fake `EventPublisher` and assert the recorded events; the subscriber's tests call the handler with an event and a unit of work; one test runs the whole flow against `moto`'s SNS and SQS.

## Code example
```
request ─▶ use case ─▶ events.outbox row   (same transaction as the change)
             commit ─▶ relay ─▶ SNS topic  (before the response is sent)
  sweeper (every minute) ─▶ SNS            (rows the relay missed)
  purge (daily)          ─▶ delete sent outbox and processed rows past retention
SNS ─▶ SQS queue per service (+ DLQ) ─▶ consumer Lambda ─▶ handler, own transaction
```

The base type and the publisher `Protocol` live in `shared/events/`, so a service's domain can use them:

```python
# app/shared/events/base.py
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)


class EventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...
```

The publisher defines the event in its domain and re-exports it from `__init__.py`:

```python
# app/services/users/domain/events.py
from dataclasses import dataclass

from app.shared.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserDeactivated(DomainEvent):
    user_id: int
```

```python
# app/services/users/__init__.py
from app.services.users.domain.events import UserDeactivated
from app.services.users.public import UsersApi

__all__ = ["UserDeactivated", "UsersApi"]
```

The use case publishes after changing state, through the `EventPublisher` it is given:

```python
# app/services/users/use_cases/deactivate_user.py
from dataclasses import dataclass

from app.services.users.domain.errors import UserNotFound
from app.services.users.domain.events import UserDeactivated
from app.services.users.domain.protocols import UserRepository
from app.shared.events.base import EventPublisher


@dataclass(frozen=True)
class DeactivateUser:
    user_id: int


def deactivate_user(
    command: DeactivateUser, users: UserRepository, events: EventPublisher
) -> None:
    user = users.get(command.user_id)
    if user is None:
        raise UserNotFound(command.user_id)
    user.deactivate()
    users.save(user)
    events.publish(UserDeactivated(user_id=command.user_id))
```

The unit of work gives use cases an `OutboxPublisher` bound to its session, so the event row commits or rolls back with the change. After commit it hands the new event IDs to the relay:

```python
# app/core/db/unit_of_work.py
from types import TracebackType
from typing import Self

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.outbox.publisher import OutboxPublisher
from app.core.outbox.relay import OutboxRelay


class UnitOfWork:
    def __init__(self, engine: Engine, relay: OutboxRelay) -> None:
        self._engine = engine
        self._relay = relay

    def __enter__(self) -> Self:
        self.session = Session(self._engine)
        self.events = OutboxPublisher(self.session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        with self.session:
            if exc_type is not None:
                self.session.rollback()
                return
            self.session.commit()
        self._relay.relay(self.events.event_ids)
```

```python
# app/core/outbox/publisher.py
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.events.messages import event_name, to_payload
from app.core.outbox.models import OutboxRow
from app.shared.events.base import DomainEvent


class OutboxPublisher:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.event_ids: list[UUID] = []

    def publish(self, event: DomainEvent) -> None:
        self._session.add(
            OutboxRow(
                event_id=event.event_id,
                event_type=event_name(type(event)),
                payload=to_payload(event),
                created_at=datetime.now(UTC),
            )
        )
        self.event_ids.append(event.event_id)
```

The relay sends rows to SNS and marks them sent, one at a time, skipping rows another relay or sweep holds. `relay()` runs after each commit and only logs a failure; `sweep()` runs on a schedule and sends whatever is still pending; `purge()` deletes rows sent before a cutoff:

```python
# app/core/outbox/relay.py
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
```

```python
# app/core/messaging/sns.py
from typing import Any

import boto3

from app.core.aws.values import CLIENT_CONFIG
from app.core.config.events import EventsSettings


class SnsSender:
    def __init__(self, topic_arn: str, client: Any) -> None:
        self._topic_arn = topic_arn
        self._client = client

    def send(self, event_type: str, body: str) -> None:
        self._client.publish(
            TopicArn=self._topic_arn,
            Message=body,
            MessageAttributes={
                "event_type": {"DataType": "String", "StringValue": event_type}
            },
        )


def build_sns_sender(events: EventsSettings) -> SnsSender:
    return SnsSender(
        events.topic_arn,
        boto3.client("sns", region_name=events.region, config=CLIENT_CONFIG),
    )
```

The topic comes from settings; the region is read from its ARN:

```python
# app/core/config/events.py
from pydantic import BaseModel, ConfigDict, Field


class EventsSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    topic_arn: str = Field(pattern=r"^arn:aws:sns:[a-z0-9-]+:\d{12}:[\w-]+$")
    sweep_batch_size: int = Field(default=100, gt=0)
    retention_days: int = Field(default=30, gt=0)

    @property
    def region(self) -> str:
        return self.topic_arn.split(":")[3]
```

Request handlers get the unit of work from a dependency with `scope="function"`, so commit and relay run when the route returns, before FastAPI sends the response:

```python
# app/core/dependencies/db.py
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from app.core.db.unit_of_work import UnitOfWork


def get_unit_of_work(request: Request) -> Iterator[UnitOfWork]:
    with UnitOfWork(request.app.state.engine, request.app.state.relay) as uow:
        yield uow


UnitOfWorkDep = Annotated[
    UnitOfWork, Depends(get_unit_of_work, scope="function")
]
```

Each subscribing service has its own consumer. It decodes the message, skips an event it already processed, and runs the handlers in one unit of work. A failure is reported as a batch item failure, so SQS retries only that message. `purge()` deletes this consumer's records older than a cutoff:

```python
# app/core/events/consumer.py
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

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
        self._handlers: dict[type[DomainEvent], list[Handler]] = defaultdict(
            list
        )

    @property
    def event_names(self) -> list[str]:
        return sorted(self._types)

    def subscribe[E: DomainEvent](
        self, event_type: type[E], handler: Handler[E]
    ) -> None:
        self._types[event_name(event_type)] = event_type
        self._handlers[event_type].append(handler)

    def handle(
        self, sqs_event: dict[str, Any]
    ) -> dict[str, list[dict[str, str]]]:
        failures = []
        for record in sqs_event["Records"]:
            try:
                self._handle(record["body"])
            except Exception:
                logger.exception(
                    "%s failed to handle message %s",
                    self.name,
                    record["messageId"],
                )
                failures.append({"itemIdentifier": record["messageId"]})
        return {"batchItemFailures": failures}

    def purge(self, processed_before: datetime) -> int:
        with Session(self._engine) as session, session.begin():
            query = delete(ProcessedEventRow).where(
                ProcessedEventRow.consumer == self.name,
                ProcessedEventRow.processed_at < processed_before,
            )
            return session.execute(query).rowcount

    def _handle(self, body: str) -> None:
        name, payload = decode(body)
        event_type = self._types.get(name)
        if event_type is None:
            logger.warning(
                "%s has no handler for %s; "
                "check the subscription's filter policy",
                self.name,
                name,
            )
            return
        event = from_payload(event_type, payload)
        with UnitOfWork(self._engine, self._relay) as uow:
            if (
                uow.session.get(ProcessedEventRow, (event.event_id, self.name))
                is not None
            ):
                return
            uow.session.add(
                ProcessedEventRow(
                    event_id=event.event_id,
                    consumer=self.name,
                    processed_at=datetime.now(UTC),
                )
            )
            for handler in self._handlers[event_type]:
                handler(event, uow)
```

The subscriber's `event_handlers/` is an entry point like `api/`: it builds the implementations from the unit of work and calls a use case of its own service:

```python
# app/services/orders/event_handlers/user_deactivated.py
from app.core.db.unit_of_work import UnitOfWork
from app.services import users
from app.services.orders.infrastructure.repositories import SqlOrderRepository
from app.services.orders.use_cases.cancel_open_orders import (
    CancelOpenOrders,
    cancel_open_orders,
)


def on_user_deactivated(event: users.UserDeactivated, uow: UnitOfWork) -> None:
    cancel_open_orders(
        CancelOpenOrders(user_id=event.user_id), SqlOrderRepository(uow.session)
    )
```

```python
# app/services/orders/event_handlers/__init__.py
from app.core.events.consumer import EventConsumer
from app.services import users
from app.services.orders.event_handlers.user_deactivated import (
    on_user_deactivated,
)


def register(consumer: EventConsumer) -> None:
    consumer.subscribe(users.UserDeactivated, on_user_deactivated)
```

`app/workers.py` is the process entry point for the Lambda functions, like `main.py` is for the API. It builds settings, the engine, the relay, and one consumer per subscribing service when the module is imported, so bad config fails the Lambda init:

```python
# app/workers.py
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.config.settings import get_settings
from app.core.db.engine import build_engine
from app.core.events.consumer import EventConsumer
from app.core.messaging.sns import build_sns_sender
from app.core.observability.log import configure_logging
from app.core.outbox.relay import OutboxRelay
from app.services.orders import event_handlers as orders_handlers


@dataclass(frozen=True)
class Workers:
    relay: OutboxRelay
    orders: EventConsumer
    retention: timedelta


def create_workers() -> Workers:
    settings = get_settings()
    configure_logging(settings.log)
    # A Lambda instance handles one event at a time:
    # one connection, kept warm between invocations
    db = settings.db.model_copy(update={"pool_size": 1, "max_overflow": 0})
    engine = build_engine(db, application_name=f"{settings.app.name}-workers")
    relay = OutboxRelay(
        engine,
        build_sns_sender(settings.events),
        settings.events.sweep_batch_size,
    )
    orders = EventConsumer("orders", engine, relay)
    orders_handlers.register(orders)
    return Workers(
        relay=relay,
        orders=orders,
        retention=timedelta(days=settings.events.retention_days),
    )


workers = create_workers()


def handle_orders_events(
    event: dict[str, Any], context: Any
) -> dict[str, list[dict[str, str]]]:
    return workers.orders.handle(event)


def sweep_outbox(event: dict[str, Any], context: Any) -> dict[str, int]:
    return {"sent": workers.relay.sweep()}


def purge_events(event: dict[str, Any], context: Any) -> dict[str, int]:
    cutoff = datetime.now(UTC) - workers.retention
    return {
        "outbox": workers.relay.purge(cutoff),
        "orders": workers.orders.purge(cutoff),
    }
```

Infrastructure, one set per subscribing service:
- **SQS queue** `shop-orders-events`, with a dead-letter queue (`maxReceiveCount` 5) and a visibility timeout of at least six times the function timeout.
- **SNS subscription** from `shop-events` to the queue, with `RawMessageDelivery` on and a `FilterPolicy` of `{"event_type": consumer.event_names}`, so the queue only receives events the service handles.
- **Lambda** `app.workers.handle_orders_events` with the queue as event source and `ReportBatchItemFailures` on.

Plus one **Lambda** `app.workers.sweep_outbox` on an EventBridge schedule (every minute), and one `app.workers.purge_events` (daily).

Users never imports orders; adding another subscriber means a new consumer, queue, and subscription, and nothing changes in users.

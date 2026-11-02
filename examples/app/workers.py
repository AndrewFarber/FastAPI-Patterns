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

from dataclasses import dataclass
from typing import Any

from app.core.config.log import configure_logging
from app.core.config.settings import get_settings
from app.core.db.engine import build_engine
from app.core.events.consumer import EventConsumer
from app.core.messaging.sns import build_sns_sender
from app.core.outbox.relay import OutboxRelay
from app.services.orders import event_handlers as orders_handlers


@dataclass(frozen=True)
class Workers:
    relay: OutboxRelay
    orders: EventConsumer


def create_workers() -> Workers:
    settings = get_settings()
    configure_logging(settings.log)
    engine = build_engine(settings.db, application_name=f"{settings.app.name}-workers")
    relay = OutboxRelay(engine, build_sns_sender(settings.events), settings.events.sweep_batch_size)
    orders = EventConsumer("orders", engine, relay)
    orders_handlers.register(orders)
    return Workers(relay=relay, orders=orders)


workers = create_workers()


def handle_orders_events(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    return workers.orders.handle(event)


def sweep_outbox(event: dict[str, Any], context: Any) -> dict[str, int]:
    return {"sent": workers.relay.sweep()}

from app.core.events.consumer import EventConsumer
from app.services import users
from app.services.orders.event_handlers.user_deactivated import (
    on_user_deactivated,
)


def register(consumer: EventConsumer) -> None:
    consumer.subscribe(users.UserDeactivated, on_user_deactivated)

from app.core.events.bus import EventBus
from app.services import users
from app.services.orders.event_handlers.user_deactivated import on_user_deactivated


def register(bus: EventBus) -> None:
    bus.subscribe(users.UserDeactivated, on_user_deactivated)

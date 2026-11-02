from dataclasses import dataclass

from app.services.users.domain.errors import UserNotFound
from app.services.users.domain.events import UserDeactivated
from app.services.users.domain.protocols import UserRepository
from app.shared.events.base import EventPublisher


@dataclass(frozen=True)
class DeactivateUser:
    user_id: int


def deactivate_user(command: DeactivateUser, users: UserRepository, events: EventPublisher) -> None:
    user = users.get(command.user_id)
    if user is None:
        raise UserNotFound(command.user_id)
    user.deactivate()
    users.save(user)
    events.publish(UserDeactivated(user_id=command.user_id))

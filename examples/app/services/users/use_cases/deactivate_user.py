from dataclasses import dataclass

from app.services.users.domain.errors import UserNotFoundError
from app.services.users.domain.events import UserDeactivated
from app.services.users.domain.protocols import UserRepository
from app.shared.events.base import EventPublisher


@dataclass(frozen=True)
class DeactivateUserCommand:
    user_id: int


def deactivate_user(
    command: DeactivateUserCommand,
    user_repository: UserRepository,
    event_publisher: EventPublisher,
) -> None:
    user = user_repository.get(command.user_id)
    if user is None:
        raise UserNotFoundError(command.user_id)
    user.deactivate()
    user_repository.save(user)
    event_publisher.publish(UserDeactivated(user_id=command.user_id))

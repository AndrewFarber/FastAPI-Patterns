import pytest

from app.services.users.domain.entities import User, UserStatus
from app.services.users.domain.errors import (
    UserAlreadyDeactivatedError,
    UserNotFoundError,
)
from app.services.users.domain.events import UserDeactivated
from app.services.users.use_cases.deactivate_user import (
    DeactivateUserCommand,
    deactivate_user,
)


class FakeUserRepository:
    def __init__(self, *users: User) -> None:
        self.users = {user.id: user for user in users}

    def get(self, user_id: int) -> User | None:
        return self.users.get(user_id)

    def add(self, user: User) -> User:
        user.id = len(self.users) + 1
        self.users[user.id] = user
        return user

    def save(self, user: User) -> None:
        self.users[user.id] = user


class FakeEventPublisher:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


def test_deactivate_publishes_the_fact():
    user_repository = FakeUserRepository(User(id=1, name="ann"))
    event_publisher = FakeEventPublisher()
    deactivate_user(
        DeactivateUserCommand(user_id=1), user_repository, event_publisher
    )
    assert user_repository.get(1).status is UserStatus.DEACTIVATED
    assert [type(e) for e in event_publisher.events] == [
        UserDeactivated
    ] and event_publisher.events[0].user_id == 1


def test_deactivate_twice_is_a_rule_violation():
    user_repository = FakeUserRepository(
        User(id=1, name="ann", status=UserStatus.DEACTIVATED)
    )
    with pytest.raises(UserAlreadyDeactivatedError):
        deactivate_user(
            DeactivateUserCommand(user_id=1),
            user_repository,
            FakeEventPublisher(),
        )


def test_deactivate_unknown_user_is_not_found():
    with pytest.raises(UserNotFoundError):
        deactivate_user(
            DeactivateUserCommand(user_id=9),
            FakeUserRepository(),
            FakeEventPublisher(),
        )

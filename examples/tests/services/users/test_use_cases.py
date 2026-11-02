import pytest

from app.services.users.domain.entities import User, UserStatus
from app.services.users.domain.errors import (
    UserAlreadyDeactivated,
    UserNotFound,
)
from app.services.users.domain.events import UserDeactivated
from app.services.users.use_cases.deactivate_user import (
    DeactivateUser,
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


class FakePublisher:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


def test_deactivate_publishes_the_fact():
    users, events = FakeUserRepository(User(id=1, name="ann")), FakePublisher()
    deactivate_user(DeactivateUser(user_id=1), users, events)
    assert users.get(1).status is UserStatus.DEACTIVATED
    assert [type(e) for e in events.events] == [
        UserDeactivated
    ] and events.events[0].user_id == 1


def test_deactivate_twice_is_a_rule_violation():
    users = FakeUserRepository(
        User(id=1, name="ann", status=UserStatus.DEACTIVATED)
    )
    with pytest.raises(UserAlreadyDeactivated):
        deactivate_user(DeactivateUser(user_id=1), users, FakePublisher())


def test_deactivate_unknown_user():
    with pytest.raises(UserNotFound):
        deactivate_user(
            DeactivateUser(user_id=9), FakeUserRepository(), FakePublisher()
        )

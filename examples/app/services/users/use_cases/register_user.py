from dataclasses import dataclass

from app.services.users.domain.entities import User
from app.services.users.domain.protocols import UserRepository


@dataclass(frozen=True)
class RegisterUserCommand:
    name: str


def register_user(
    command: RegisterUserCommand, user_repository: UserRepository
) -> User:
    return user_repository.add(User(name=command.name))

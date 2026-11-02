from dataclasses import dataclass

from app.services.users.domain.entities import User
from app.services.users.domain.protocols import UserRepository


@dataclass(frozen=True)
class RegisterUser:
    name: str


def register_user(command: RegisterUser, users: UserRepository) -> User:
    return users.add(User(name=command.name))

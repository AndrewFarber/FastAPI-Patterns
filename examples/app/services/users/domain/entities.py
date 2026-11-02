from dataclasses import dataclass
from enum import StrEnum

from app.services.users.domain.errors import UserAlreadyDeactivated


class UserStatus(StrEnum):
    ACTIVE = "active"
    DEACTIVATED = "deactivated"


@dataclass
class User:
    name: str
    status: UserStatus = UserStatus.ACTIVE
    id: int | None = None
    version: int = 0

    def is_active(self) -> bool:
        return self.status is UserStatus.ACTIVE

    def deactivate(self) -> None:
        if not self.is_active():
            raise UserAlreadyDeactivated(self.id)
        self.status = UserStatus.DEACTIVATED

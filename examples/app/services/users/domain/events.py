from dataclasses import dataclass

from app.shared.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserDeactivated(DomainEvent):
    user_id: int

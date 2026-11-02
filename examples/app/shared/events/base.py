from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)


class EventPublisher(Protocol):
    def publish(self, event: DomainEvent) -> None: ...

import json
from typing import Any

from pydantic import TypeAdapter

from app.shared.events.base import DomainEvent


def event_name(event_type: type[DomainEvent]) -> str:
    return event_type.__name__


def to_payload(event: DomainEvent) -> dict[str, Any]:
    return TypeAdapter(type(event)).dump_python(event, mode="json")


def from_payload[E: DomainEvent](event_type: type[E], payload: dict[str, Any]) -> E:
    return TypeAdapter(event_type).validate_python(payload)


def encode(event_type: str, payload: dict[str, Any]) -> str:
    return json.dumps({"event_type": event_type, "payload": payload})


def decode(body: str) -> tuple[str, dict[str, Any]]:
    message = json.loads(body)
    return message["event_type"], message["payload"]

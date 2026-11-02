from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RotatedSecretAuth(BaseModel):
    """A password rotated by Secrets Manager, read per new connection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["rotated_secret"]
    secret_id: str                                  # the secret's ARN (a name works too)
    region: str
    ttl_seconds: float = Field(default=300, gt=0)   # how long to cache the secret

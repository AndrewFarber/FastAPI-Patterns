from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RotatedSecretAuth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["rotated_secret"]
    secret_id: str
    region: str
    ttl_seconds: float = Field(default=300, gt=0)

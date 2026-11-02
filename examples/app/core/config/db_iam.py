from typing import Literal

from pydantic import BaseModel, ConfigDict


class IamAuth(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["iam"]
    region: str

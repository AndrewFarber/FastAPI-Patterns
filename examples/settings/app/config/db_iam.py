from typing import Literal

from pydantic import BaseModel, ConfigDict


class IamAuth(BaseModel):
    """AWS IAM database authentication: a fresh token per connection, no password."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["iam"]
    region: str                                     # region of the RDS instance

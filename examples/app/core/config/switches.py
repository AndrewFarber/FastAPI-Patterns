from pydantic import BaseModel, ConfigDict, Field


class SwitchSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    region: str
    ttl_seconds: float = Field(default=30, gt=0)
    orders_paused: str = Field(pattern=r"^/")

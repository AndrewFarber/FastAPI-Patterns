from pydantic import BaseModel, ConfigDict


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "shop-api"
    is_prd: bool
    debug: bool = False

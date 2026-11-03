from pydantic import BaseModel, ConfigDict


class FeaturesSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    new_checkout: bool = False
    bulk_export: bool = False

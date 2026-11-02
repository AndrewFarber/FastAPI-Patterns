from pydantic import BaseModel, ConfigDict


class FeatureSettings(BaseModel):
    """Static feature flags: fixed for the life of the process, changed by redeploying."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # One bool per feature, named for the feature, default off
    new_checkout: bool = False       # services: switch to the new checkout flow
    bulk_export: bool = False        # main.py: mount the /exports router

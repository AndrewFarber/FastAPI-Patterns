from pydantic import BaseModel, ConfigDict


class RuntimeFlagsSource(BaseModel):
    """Where AppConfig Agent finds the runtime flags (2f-settings-feature-flags-appconfig)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    application: str
    environment: str                 # the AppConfig environment ("dev", "staging", "prd"): set per stage, not derived
    profile: str = "runtime-flags"


class FeatureSettings(BaseModel):
    """Static feature flags: fixed for the life of the process, changed by redeploying."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # One bool per feature, named for the feature, default off
    new_checkout: bool = False       # services: switch to the new checkout flow
    bulk_export: bool = False        # main.py: mount the /exports router
    # A handful of user IDs that see beta features early. Env vars share 4 KB on Lambda:
    # longer lists belong in AppConfig or Parameter Store.
    beta_users: frozenset[str] = frozenset()

    # Runtime flags from AppConfig; None (local dev, no agent) = runtime flags keep their defaults
    runtime_flags: RuntimeFlagsSource | None = None

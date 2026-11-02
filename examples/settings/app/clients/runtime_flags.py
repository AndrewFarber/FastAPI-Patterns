import http.client
import logging
import time
import urllib.request

from pydantic import BaseModel, ConfigDict, TypeAdapter

logger = logging.getLogger(__name__)


class RuntimeFlags(BaseModel):
    """Flags that change without a deploy. Static flags stay in FeatureSettings."""

    model_config = ConfigDict(frozen=True, extra="ignore")   # flags added in AppConfig first are ignored

    payments_kill_switch: bool = False
    new_checkout_rollout: bool = False


class _Flag(BaseModel):
    model_config = ConfigDict(extra="ignore")                 # flag attributes besides "enabled" are ignored

    enabled: bool


# A feature flag profile, as the agent serves it: {"payments_kill_switch": {"enabled": true}, ...}
_payload = TypeAdapter(dict[str, _Flag])


class AppConfigFlags:
    """Reads RuntimeFlags from AppConfig Agent on localhost. One per process (on Lambda: per execution environment)."""

    def __init__(
        self, application: str, environment: str, profile: str,
        timeout_seconds: float = 0.5, retry_after_seconds: float = 10.0,
    ) -> None:
        self._url = (
            f"http://localhost:2772/applications/{application}"
            f"/environments/{environment}/configurations/{profile}"
        )
        self._timeout = timeout_seconds
        self._retry_after = retry_after_seconds
        self._retry_at = 0.0
        self._last = RuntimeFlags()                           # all off until the first successful read

    def get(self) -> RuntimeFlags:
        if time.monotonic() < self._retry_at:
            return self._last                                 # the agent failed recently: don't wait on it every request
        try:
            with urllib.request.urlopen(self._url, timeout=self._timeout) as response:
                payload = _payload.validate_json(response.read())
            self._last = RuntimeFlags.model_validate({name: flag.enabled for name, flag in payload.items()})
        # Agent down or slow, broken response, or a payload of the wrong shape (ValidationError is a ValueError)
        except (OSError, http.client.HTTPException, ValueError) as exc:
            self._retry_at = time.monotonic() + self._retry_after
            logger.warning("reading flags from AppConfig Agent failed, using the last good flags: %s", exc)
        return self._last

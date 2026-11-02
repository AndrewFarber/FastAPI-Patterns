---
title: "Build metadata"
category: project-structure
tags: [settings, build-metadata, docker, deployment]
status: draft
related: ["[[2a-settings-app]]", "[[1a-settings-management]]", "[[1b-settings-access]]"]
---

# Build metadata

CI bakes the version, git SHA, and build time into the image as env vars, and `AppSettings` validates them like any other setting. A log filter adds the release and the platform's immutable deployed version to every record, so the running app can always say which build it is, even with two versions live.

## Fits when
- The app is built in CI and deployed as a container image.
- More than one version runs at once: canary, linear, a rollback.

Not when:
- Never worth skipping; it costs three optional fields.

## Signals
- **Feature:** "show the version", "which commit is deployed", a `/version` endpoint, "which version logged this", canary rollouts.
- **Code:** a hard-coded `__version__`; reading a `VERSION` file or `git` at runtime; a `deployment` or `environment` field in the image; a `"canary"` label in logs; a filter on one named logger (`getLogger("orders").addFilter`).

## Pattern
```python
# app/config/app.py
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "orders-api"
    is_prd: bool = False
    debug: bool = False

    # Build metadata: baked into the image by CI, None when running locally
    version: str | None = None
    git_sha: str | None = Field(default=None, pattern=r"^[0-9a-f]{7,40}$")
    build_time: AwareDatetime | None = None   # "2026-11-02T10:00:00Z"; a time without a zone is rejected
```

```dockerfile
# Dockerfile (fragment: the full file is examples/settings/Dockerfile)
# Build metadata last: these values change every build, so the layers above stay cached.
# An empty value would fail settings validation at startup; fail the build instead.
ARG VERSION GIT_SHA BUILD_TIME
RUN test -n "$VERSION" && test -n "$GIT_SHA" && test -n "$BUILD_TIME" \
    || { echo "set --build-arg VERSION, GIT_SHA and BUILD_TIME" >&2; exit 1; }
ENV APP__VERSION=$VERSION \
    APP__GIT_SHA=$GIT_SHA \
    APP__BUILD_TIME=$BUILD_TIME
```

```bash
docker build --build-arg VERSION=1.4.2 --build-arg GIT_SHA=$(git rev-parse HEAD) \
  --build-arg BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ) .
```

Tag every log record with the release and the deployed version:

```python
# app/observability.py
import logging
import os

from app.config.app import AppSettings


class DeploymentFilter(logging.Filter):
    """Adds the release and the Lambda function version to every log record."""

    def __init__(self, app: AppSettings) -> None:
        super().__init__()
        self.version = app.version            # the release, from the image ("1.4.2")
        # The published Lambda version ("7"), set by Lambda: immutable, unlike a "canary" label.
        # A flag change without a new release is a new version too. None when not on Lambda.
        self.function_version = os.environ.get("AWS_LAMBDA_FUNCTION_VERSION")

    def filter(self, record: logging.LogRecord) -> bool:
        record.version = self.version
        record.function_version = self.function_version
        return True
```

```python
# app/main.py (fragment)
configure_logging(settings.log, DeploymentFilter(settings.app))
```

## Rules
- **Optional fields, `None` locally.** Only CI builds set them.
- **Validate them:** `git_sha` has a hex pattern (catches a branch name); `build_time` is an `AwareDatetime` (a time without a zone is rejected).
- **Only build facts in the image.** The same image is promoted between environments; which deployment runs it is not a build fact.
- **Identify a deployment by the platform's immutable version:** `AWS_LAMBDA_FUNCTION_VERSION` on Lambda. It also tells apart two versions of one release with different env vars. Read it in `observability.py`, the one `os.environ` read outside `config/` ([[1a-settings-management]]).
- **Filters go on the handler,** not a named logger, so records from every logger carry the fields. Use the same value as a metric dimension.
- **`/healthz` returns `version`** ([[1b-settings-access]]).

## Anti-patterns
- **Unguarded build args.** An unset `ARG` is an empty string: the image builds, then every instance fails startup on `APP__GIT_SHA=""`.
- **A `canary` label as identity.** After promotion the version keeps reporting `canary`.
- **Build args early in the Dockerfile.** Every layer after them, dependencies included, rebuilds every time.

## Related
- [[2a-settings-app]]
- [[1a-settings-management]]
- [[1b-settings-access]]

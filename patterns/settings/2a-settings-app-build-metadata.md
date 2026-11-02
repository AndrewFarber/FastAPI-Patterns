---
title: "Build metadata"
category: project-structure
tags: [settings, build-metadata, docker, deployment]
status: draft
related: ["[[2a-settings-app]]", "[[1d-settings-deployments]]", "[[1e-settings-lambda]]"]
---

# Build metadata

## Problem
When something breaks, the first question is which build is running. Without the version and commit in the app itself, the answer depends on deploy logs, and during a rollout the new version can't be told apart from the old one in logs and metrics.

## Use when
- The app is built in CI and deployed as a container image (on Lambda: [[1e-settings-lambda]]).

## Avoid when
- Never; it costs three optional fields.

## Solution
Add the build metadata to `AppSettings` ([[2a-settings-app]]):

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

CI passes the values as build args; the Dockerfile turns them into env vars inside the image.

```dockerfile
# Dockerfile (fragment: the full file is in 1e-settings-lambda)
# Build metadata last: these values change every build, so the layers above stay cached.
# An empty value would fail settings validation at init; fail the build instead.
ARG VERSION GIT_SHA BUILD_TIME
RUN test -n "$VERSION" && test -n "$GIT_SHA" && test -n "$BUILD_TIME" \
    || { echo "set --build-arg VERSION, GIT_SHA and BUILD_TIME" >&2; exit 1; }
ENV APP__VERSION=$VERSION \
    APP__GIT_SHA=$GIT_SHA \
    APP__BUILD_TIME=$BUILD_TIME
```

```bash
docker build \
  --build-arg VERSION=1.4.2 \
  --build-arg GIT_SHA=$(git rev-parse HEAD) \
  --build-arg BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ) \
  -t orders-api:1.4.2 .
```

- **`build_time` is an `AwareDatetime`.** `date -u ...Z` carries its zone; a time without one is rejected rather than guessed.
- **No `deployment` field.** The same image is promoted unchanged, so which deployment runs it is not a build fact. On Lambda, identify a deployment by the published function version, `AWS_LAMBDA_FUNCTION_VERSION`, which Lambda sets in every execution environment and which never changes. A role label like `canary` doesn't work as an identity: after promotion the version would keep reporting `canary`. [[1d-settings-deployments]] shows how it reaches the logs.
- **Per-environment values** (`APP__IS_PRD`, hosts) are function env vars set by the deployment. Lambda freezes them into each published version, so changing one means publishing a new version.
- `/healthz` returns `version` ([[1b-settings-access]]), so anyone can see what's deployed.

## Pitfalls
- **Missing build args.** An unset `ARG` is an empty string: the image builds, then every execution environment fails init on `APP__GIT_SHA=""`. The `test -n` guard fails the build instead.
- **Unvalidated build metadata.** The `git_sha` pattern catches a build that passed a branch name.
- **Build args early in the Dockerfile.** They change every build, so every layer after them is rebuilt, dependencies included.
- **Baking deployment-specific values into the image.** Only build facts belong in it.

## Related
- [[2a-settings-app]]
- [[1d-settings-deployments]]
- [[1e-settings-lambda]]

---
title: "Settings in canary and linear deployments"
category: project-structure
tags: [settings, deployment, canary, logging]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[1b-settings-access]]", "[[2a-settings-app-build-metadata]]", "[[2f-settings-feature-flags-appconfig]]", "[[3b-settings-aws-sources]]"]
---

# Settings in canary and linear deployments

While two versions run at once, tag every log line with an identity that never changes, and change shared configuration in steps (expand, then contract) so neither version sees a value it rejects or misses one it requires.

## Fits when
- More than one version of the app runs at the same time: canary, linear, blue/green, or a rollback.

Not when:
- Stop-the-world deploys only. Even then, a rollback restarts the old version against the current shared config.

## Signals
- **Feature:** "canary", "rollout", "rollback", "which version logged this"; adding, removing, or renaming a setting stored in Parameter Store or Secrets Manager.
- **Code:** a `deployment: str` or `stage = "canary"` label in logs or settings; a log filter on one named logger (`getLogger("orders").addFilter`); a new required field in a PR that also adds the value to shared config.

## Pattern

### Tag logs with the immutable version
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

- `version` says which release; `function_version` (`AWS_LAMBDA_FUNCTION_VERSION`, set by Lambda) says which published version, and also tells apart two versions of one release with different env vars.
- Use the same value as a dimension for the app's own metrics.

### Change shared config by expand, then contract
Both versions read the same Parameter Store path and secret ([[3b-settings-aws-sources]]), and `extra="forbid"` rejects what a version doesn't know.

- **Add a field:** release a version that declares it with a default → once no older version can get traffic (rollbacks included), add the value → later, optionally drop the default.
- **Remove a field:** release a version that stops using it but still declares it → once no older version can get traffic, delete the value → later, delete the field.
- **Rename** = add the new field + remove the old one.
- **Large changes:** give each release its own parameter path (`AWS_SSM_PATH=/orders/prd/releases/1.4.2`) in its env vars; keep secrets shared.

## Rules
- **Bad config fails startup** ([[1b-settings-access]]), so a rollout's error alarm catches it. Alarm on both failed invocations and 5xx: each misses the other.
- **Per-version values live in env vars,** which are frozen into each published version; they change with the code and need no ordering.
- **Runtime flags bypass the app's canary.** They reach every version at once; roll them out with AppConfig ([[2f-settings-feature-flags-appconfig]]).
- **Filters go on the handler,** not a named logger, so records from every logger carry the fields.

## Anti-patterns
- **A `canary` label as identity.** After promotion the version keeps reporting `canary`.
- **Adding a value to shared config before every runnable version accepts it.** The old version's next cold start fails.
- **Deleting a field and its value in one release.** The old version still requires it.
- **Relaxing `extra="forbid"` to ease deploys.** Typos are silently ignored again; use expand-then-contract.
- **Baking deploy-specific values into the image.** The same image is promoted between environments.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[1b-settings-access]]
- [[2a-settings-app-build-metadata]]
- [[2f-settings-feature-flags-appconfig]]
- [[3b-settings-aws-sources]]

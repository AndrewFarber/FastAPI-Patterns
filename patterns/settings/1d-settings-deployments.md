---
title: "Settings in canary and linear deployments"
category: project-structure
tags: [settings, deployment, canary, aws-lambda, codedeploy]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[1e-settings-lambda]]", "[[1d-settings-deployments-shared-config]]", "[[1d-settings-deployments-appconfig-rollouts]]", "[[2a-settings-app-build-metadata]]"]
---

# Settings in canary and linear deployments

## Problem
During a canary or linear deployment, two versions of the app run at once. Each needs settings it understands, a bad configuration must stop a rollout rather than take traffic, and logs and metrics must show which version did what.

## Use when
- More than one version of the app runs at the same time: canary, linear, or a rollback.

## Avoid when
- Never; every deployment strategy except stop-the-world has two versions running at some point.

## Solution

### How a Lambda rollout works
Each deploy publishes a new Lambda version. A published version is immutable: its image digest and env vars are frozen. Traffic goes to the `live` alias (the Function URL sits on it), and CodeDeploy shifts the alias's weights from the old version to the new one, watching CloudWatch alarms. If an alarm fires, it points the alias back at the old version. General Lambda behaviour is in [[1e-settings-lambda]].

### What already works
- **Per-version env vars.** Each published version has its own env vars, including static feature flags ([[2f-settings-feature-flags]]). A version published with `FEATURES__NEW_CHECKOUT=true` can take 10% of the traffic while the old version keeps it off.
- **Bad config fails init.** Settings are validated when `app.main` is imported ([[1b-settings-access]]). A misconfigured version never finishes init, so every request routed to it fails and counts in the alias's `Errors` metric, which the CodeDeploy alarm watches ([[1e-settings-lambda]]).
- **Rotated secrets.** Passwords from [[2b-settings-db-rotated-password]] and IAM tokens from [[2b-settings-db-iam-auth]] are fetched per connection, so both versions keep connecting through a rotation.

### Rolling out with CodeDeploy
A CodeDeploy deployment group on the `live` alias, with a canary or linear configuration (e.g. `LambdaCanary10Percent5Minutes`), automatic rollback, and a CloudWatch alarm on the alias's `Errors` metric (1-minute period, threshold 1, missing data not breaching). When the alarm fires, CodeDeploy points the alias back at the old version.

- **`Errors` counts failed invocations** (init errors, crashes, timeouts), not 500 responses: through LWA, a 500 is a successful invocation. To also catch a version that starts but answers 500, alarm on a 5xx metric from the app's logs.
- **To catch bad config before any traffic**, add a `pre_hook` function that invokes the new version (e.g. `GET /healthz`) and reports the result to CodeDeploy. Without it, the canary's share of requests fails until the alarm fires.
- **Rollback targets stay invocable.** Old published versions keep existing (unless deleted), so a rollback starts fresh environments of the old version. They read shared configuration again at init ([[1d-settings-deployments-shared-config]]).

### Tagging each version
Tag every log line and metric with an identity that never changes: `AWS_LAMBDA_FUNCTION_VERSION` (`"7"`), which Lambda sets in each execution environment. A label like `canary` doesn't work: once promoted, the version would keep reporting `canary` for the rest of its life. The function version also tells apart two versions of the same release with different flags, which `AppSettings.version` ([[2a-settings-app-build-metadata]]) can't.

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

`create_app()` attaches it to the root handler, so records from every logger carry both fields ([[1a-settings-management]]):

```python
# app/main.py (fragment)
configure_logging(settings.log, DeploymentFilter(settings.app))
```

- Lambda's own metrics for the alias have an `ExecutedVersion` dimension, so dashboards can split them by version without app changes. Use the same value as a dimension for the app's own metrics.
- With the Powertools Logger instead of `logging`, `logger.append_keys(function_version=...)` does the same.

### Specific cases
| Need | Note |
|---|---|
| Versions share configuration in Parameter Store or Secrets Manager | [[1d-settings-deployments-shared-config]] |
| Runtime flags or refreshed values must roll out gradually | [[1d-settings-deployments-appconfig-rollouts]] |

## Pitfalls
- **Lazy settings validation.** If settings are built on the first request, init succeeds, the version takes traffic, and only then fails.
- **Alarming only on 500 responses, or only on `Errors`.** Each misses the other failure mode; bad config shows up only in `Errors`.
- **Filtering a single named logger.** A filter on `logging.getLogger("orders")` misses records from `app.orders.service` and libraries; attach it to the handler.
- **Baking deploy-specific values into the image.** The same image is promoted unchanged between environments; per-environment values go into the function's env vars.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[1e-settings-lambda]]
- [[1d-settings-deployments-shared-config]]
- [[1d-settings-deployments-appconfig-rollouts]]
- [[2a-settings-app-build-metadata]]

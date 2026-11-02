---
title: "Settings from AWS sources"
category: project-structure
tags: [settings, aws, secrets-manager, parameter-store, aws-lambda]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[1e-settings-lambda]]", "[[3a-settings-secret-files]]", "[[3b-settings-aws-sources-pydantic]]"]
---

# Settings from AWS sources

## Problem
Secrets and environment-specific configuration live in AWS Secrets Manager and Parameter Store. Copying them into env vars by hand leaks secrets into deploy scripts and drifts out of date; fetching them with ad hoc `boto3` calls bypasses the validation in `Settings`. Lambda has no secret injection like ECS's task-definition `secrets`: whatever ends up in an env var is plain text in the function configuration ([[1e-settings-lambda]]).

## Use when
- The app runs on AWS and its secrets or configuration live in Secrets Manager or Parameter Store.

## Avoid when
- Local development and tests: plain env vars ([[1a-settings-management]]) or secret files ([[3a-settings-secret-files]]).

## Solution
Pick by when the value is resolved and whether it is secret:

| Value | Resolved | How |
|---|---|---|
| Non-secret configuration (host, pool size, client IDs) | At deploy, into an env var | Set it in the stack, or read a parameter at deploy time (below) |
| Secrets, or too many values for 4 KB of env vars | At init, by the app | pydantic-settings AWS sources: [[3b-settings-aws-sources-pydantic]] |
| A rotated DB password | Per new connection | [[2b-settings-db-rotated-password]] |
| Values that must change while the app runs | On a TTL | [[4a-settings-refreshing-values]] |

Non-secret parameters resolved at deploy time with AWS CDK:

```python
# infra/service_stack.py (fragment)
from aws_cdk import aws_ssm as ssm

environment={
    # Resolved by CloudFormation at deploy time, then frozen into the published version
    "DB__HOST": ssm.StringParameter.value_for_string_parameter(self, "/orders/prd/db/host"),
    # A secret: pass only its ARN; the app reads the value and needs read access
    "DB__AUTH__SECRET_ID": database.app_secret.secret_arn,
},
```

- **Deploy-time values** need a redeploy to change, which also publishes a new version that CodeDeploy rolls out ([[1d-settings-deployments]]).
- **Secret values never go through env vars,** not even as `{{resolve:secretsmanager:...}}`: CloudFormation resolves it into plain text in the function configuration.
- **The AWS Parameters and Secrets Lambda Extension** doesn't set env vars either: it serves values over HTTP on `localhost:2773`. The app would still need code to call it; for values read once at init the pydantic-settings sources do the same with no extra component.
- **Powertools for AWS Lambda** (`parameters` utility) is a cached client for values read at runtime, an alternative to the caches in [[4a-settings-refreshing-values-cache]], not a settings source.

## Pitfalls
- **Secrets in the function's `environment`.** Visible to anyone with `lambda:GetFunctionConfiguration`, and copied into every published version.
- **Freezing rotated secrets.** A password resolved at deploy or init stops working after a rotation; read it per connection ([[2b-settings-db-rotated-password]]).
- **Assuming ECS-style injection.** Patterns from ECS (`secrets` with `valueFrom`) and EKS (External Secrets, CSI volumes) have no Lambda equivalent.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[1e-settings-lambda]]
- [[3a-settings-secret-files]]
- [[3b-settings-aws-sources-pydantic]]

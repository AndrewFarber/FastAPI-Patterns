---
title: "Rolling out runtime configuration with AppConfig"
category: project-structure
tags: [settings, deployment, canary, aws-appconfig, aws-lambda]
status: draft
related: ["[[1d-settings-deployments]]", "[[1e-settings-lambda]]", "[[2f-settings-feature-flags-appconfig]]"]
---

# Rolling out runtime configuration with AppConfig

## Problem
Runtime flags ([[2f-settings-feature-flags-appconfig]]) and refreshed values ([[4a-settings-refreshing-values]]) reach every running Lambda version at once, so a CodeDeploy canary of the app ([[1d-settings-deployments]]) doesn't protect against a bad flag change.

## Use when
- Runtime flags or other configuration live in AWS AppConfig.

## Avoid when
- The configuration only changes with a deploy: the app's own canary covers it.

## Solution
AWS AppConfig rolls configuration out gradually, using a deployment strategy chosen per change:

| Strategy | Rollout |
|---|---|
| `AppConfig.Linear20PercentEvery6Minutes` | 20% of targets every 6 minutes, 30 minute bake time. AWS-recommended for production. |
| `AppConfig.Canary10Percent20Minutes` | Exponential from 10% over 20 minutes, 10 minute bake time. AWS-recommended for production. |
| `AppConfig.AllAtOnce` | Everything at once, 10 minute bake time. For urgent changes like a kill switch. |

- **A target is an agent session.** On Lambda, the AppConfig Agent extension in each execution environment is one target ([[1e-settings-lambda]]). "20%" means 20% of environments, so one user's requests can land on both the old and the new configuration.
- **Per-user consistency:** send an `Entity-Id` header (a user or tenant ID) with each request to the agent (agent 2.0.136060 or later). During the rollout, the agent keeps serving that entity the same configuration version, whichever environment handles the request.
- **Automatic rollback:** AppConfig watches the environment's CloudWatch alarms during the rollout and the bake time, and rolls the configuration back if one fires. Attach the alarms that would catch a bad flag (5xx rate, latency), and give each monitor an IAM role (`AlarmRoleArn`) that allows `cloudwatch:DescribeAlarms`; without it AppConfig can't read the alarm.
- **Kill switches** should use `AllAtOnce`: they exist to act fast.

## Pitfalls
- **Assuming an app canary covers configuration.** Runtime changes reach every version at once; roll them out with a deployment strategy.
- **No alarms attached, or no alarm role.** Without them, a gradual rollout only slows a bad change down; it never rolls it back.
- **A kill switch stuck behind a rollout.** AppConfig runs one deployment per environment at a time, so a kill switch can't start while a 30-minute linear rollout is still going. Stop that rollout first (which rolls it back), or keep kill switches in their own AppConfig environment, which the app reads as a second configuration.
- **Overlapping with a CodeDeploy rollout.** When a flag rollout and an app canary run together, an alarm both watch rolls back both, and doesn't say which change caused it. Run one at a time.

## Related
- [[1d-settings-deployments]]
- [[1e-settings-lambda]]
- [[2f-settings-feature-flags-appconfig]]

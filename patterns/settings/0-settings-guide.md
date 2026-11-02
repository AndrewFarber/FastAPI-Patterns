---
title: "Settings guide"
category: project-structure
tags: [settings, guide]
status: draft
related: ["[[1a-settings-management]]", "[[1e-settings-lambda]]"]
---

# Settings guide

General notes come first; indented notes are specific capabilities built on the note above them.

Runtime: the notes assume the app runs on AWS Lambda as a container image behind the AWS Lambda Web Adapter, with a Function URL in front; [[1e-settings-lambda]] explains what that changes. Most notes apply to any server.

## 1. Core
- [[1a-settings-management]]: the `config/` package, root `Settings` class, env vars, rules. Start here.
- [[1b-settings-access]]: creating and reading settings: singleton, cached function (the example uses it), or app factory.
- [[1c-settings-testing]]: test fixtures for settings.
- [[1d-settings-deployments]]: settings with two versions running: startup validation, tagging versions.
    - [[1d-settings-deployments-shared-config]]: changing shared AWS config safely (expand, then contract).
    - [[1d-settings-deployments-appconfig-rollouts]]: rolling out runtime configuration gradually with AppConfig.
- [[1e-settings-lambda]]: how settings behave on Lambda: init vs invoke, failing init, env var limits, caches, DB pool, CORS.

## 2. Sub-models
- [[2a-settings-app]]: app name, production toggle, debug.
    - [[2a-settings-app-build-metadata]]: version, git SHA, build time; deployment identity is the Lambda function version.
- [[2b-settings-db]]: database connection, password auth, TLS, pool.
    - [[2b-settings-db-rds-tls]]: TLS to Amazon RDS, RDS Proxy.
    - [[2b-settings-db-iam-auth]]: AWS IAM database authentication.
    - [[2b-settings-db-rotated-password]]: passwords rotated by Secrets Manager, picked up without a restart.
- [[2c-settings-auth]]: verifying tokens from any OIDC identity provider.
    - [[2c-settings-auth-cognito]]: AWS Cognito.
- [[2d-settings-cors]]: allowed browser origins.
- [[2e-settings-email]]: SMTP settings.
- [[2f-settings-feature-flags]]: static feature flags, changed by redeploying.
    - [[2f-settings-feature-flags-appconfig]]: runtime flags from AWS AppConfig: kill switches, rollouts.

## 3. Sources
- [[3a-settings-secret-files]]: secrets as files, for local docker-compose development (Lambda has no file-mounted secrets).
- [[3b-settings-aws-sources]]: getting AWS secrets and parameters into settings; Lambda has no platform injection, so the app reads them ([[1e-settings-lambda]]).
    - [[3b-settings-aws-sources-pydantic]]: the app reads Secrets Manager and Parameter Store itself.

## 4. Values that change at runtime
- [[4a-settings-refreshing-values]]: when to refresh instead of restarting, and which option to use.
    - [[4a-settings-refreshing-values-ttl]]: rebuilding all settings on a TTL.
    - [[4a-settings-refreshing-values-cache]]: caching individual live values from AWS.

## Related
- [[1a-settings-management]]
- [[1e-settings-lambda]]

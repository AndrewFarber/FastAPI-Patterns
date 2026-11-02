---
title: "Shared configuration across deployments"
category: project-structure
tags: [settings, deployment, canary, aws, aws-lambda]
status: draft
related: ["[[1d-settings-deployments]]", "[[1e-settings-lambda]]", "[[3b-settings-aws-sources-pydantic]]"]
---

# Shared configuration across deployments

## Problem
The old and new Lambda versions usually read the same Parameter Store path and Secrets Manager secret ([[3b-settings-aws-sources-pydantic]]). With `extra="forbid"`, a value added for the new version makes the old version fail init, and a value removed for the new version can break it the same way in reverse.

## Use when
- Two versions run at once and read configuration from a shared store (Parameter Store, Secrets Manager).

## Avoid when
- All configuration is in the function's env vars: each published version freezes its own values with its code.

## Solution

### When each version reads
Every new execution environment reads the shared store at init ([[1e-settings-lambda]]); warm environments keep what they read. Environments of the old version keep starting throughout a rollout (bursts, recycled environments) and again on a rollback, so the old version re-reads the store long after its first deploy. There is no SnapStart for container images, so no environment starts from a snapshot of old values.

### Expand, then contract
Change shared configuration in steps, so no version that can still run ever sees a value it rejects or misses a value it requires.

**Adding a field:**
1. Release a version that declares the field with a default (or as optional). It accepts the value being absent.
2. Once no older version can get traffic anymore (including by rollback), add the value to Parameter Store or Secrets Manager.
3. Optionally, in a later release, remove the default to make the field required.

**Removing a field:**
1. Release a version that no longer uses the field but still declares it, so the value is still accepted.
2. Once no older version can get traffic anymore, delete the value from Parameter Store or Secrets Manager.
3. In a later release, delete the field.

**Renaming** is adding the new field and removing the old one, using both procedures.

- **"No older version can get traffic" includes rollbacks.** Old published versions stay invocable, and CodeDeploy rolls back by pointing the `live` alias at the previous one ([[1d-settings-deployments]]). Don't add values the previous version would reject until the new release has finished its rollout and is itself the rollback target.
- **Env vars don't need these steps.** Each version's env vars are frozen into it, so they change together with the code.

### Alternative: configuration per release
For large changes, give each release its own copy of the shared configuration, and point each version at its copy in the function's env vars:

```bash
# Env var of the version published for release 1.4.2
AWS_SSM_PATH=/orders/prd/releases/1.4.2
```

- Each version reads only values it was built for, so no ordering is needed, and a rollback finds its own copy.
- CI copies the parameters for each release, and old copies need cleaning up once no version that reads them can be rolled back to.
- Keep secrets shared (one secret per environment) and use expand-then-contract for them; copying secrets per release multiplies rotation work.

## Pitfalls
- **Adding a value to shared config before every version that can run accepts it.** With `extra="forbid"`, the old version's next cold start fails init (a burst, a recycled environment, a rollback).
- **Deleting a field and its value in the same release.** The old version still running requires the value; delete the value only after the old version can no longer get traffic.
- **Relaxing `extra="forbid"` to make deployments easier.** It brings back silently ignored typos. Use expand-then-contract instead.
- **Shared database schema.** Both versions use one schema, so migrations need the same expand-then-contract steps.

## Related
- [[1d-settings-deployments]]
- [[1e-settings-lambda]]
- [[3b-settings-aws-sources-pydantic]]

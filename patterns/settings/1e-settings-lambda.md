---
title: "Settings on AWS Lambda"
category: project-structure
tags: [settings, aws-lambda, lambda-web-adapter, deployment]
status: draft
related: ["[[0-settings-guide]]", "[[1a-settings-management]]", "[[1b-settings-access]]", "[[1d-settings-deployments]]", "[[2b-settings-db]]", "[[2d-settings-cors]]", "[[3b-settings-aws-sources-pydantic]]"]
---

# Settings on AWS Lambda

## Problem
On Lambda the app has no long-lived server: execution environments start and stop on demand, each handles one request at a time, env vars are small and readable by anyone who can read the function's configuration, and there is no health check. Settings have to be built at the right moment, fail in a way the rollout notices, and keep secrets out of the function configuration.

## Use when
- The FastAPI app runs on Lambda as a container image behind the AWS Lambda Web Adapter (LWA), the runtime these notes assume.

## Avoid when
- The app runs as a long-lived server (ECS, EKS, a VM). The other notes still apply; skip the Lambda specifics here.

## Solution

### How the app runs
LWA is a Lambda extension copied into the image. At init it starts alongside the container's `CMD` (uvicorn on port 8080), polls `AWS_LWA_READINESS_CHECK_PATH` until the app answers, then turns each invocation into an HTTP request to uvicorn.

```dockerfile
# Dockerfile
# syntax=docker/dockerfile:1
# Build from examples/ (the lockfile lives there):
#   docker build -f settings/Dockerfile --build-arg VERSION=... --build-arg GIT_SHA=... --build-arg BUILD_TIME=... .

# AppConfig Agent Lambda extension (runtime flags on localhost:2772). Download the layer
# zip first, see 2f-settings-feature-flags-appconfig
FROM public.ecr.aws/docker/library/python:3.14-slim AS appconfig-extension
RUN apt-get update && apt-get install -y --no-install-recommends unzip   # keeps the binaries' exec bits
COPY settings/appconfig-extension.zip /tmp/
RUN unzip /tmp/appconfig-extension.zip -d /opt

FROM public.ecr.aws/docker/library/python:3.14-slim
# COPY merges into /opt: the agent lands next to the Lambda Web Adapter in /opt/extensions
COPY --from=appconfig-extension /opt /opt

# Lambda Web Adapter: a Lambda extension that starts with the container, waits until
# the readiness path answers, then turns each invocation into an HTTP request to uvicorn
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/healthz \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# CA bundles for DB__SSLROOTCERT. Files added from a URL are mode 600, and Lambda
# runs the image as a non-root user, so make them readable.
# RDS instances: the RDS global bundle
ADD --chmod=644 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/rds-global-bundle.pem
# RDS Proxy: the Amazon Trust Services roots behind its ACM certificate, in one file
ADD --chmod=644 https://www.amazontrust.com/repository/AmazonRootCA1.pem \
    https://www.amazontrust.com/repository/AmazonRootCA2.pem \
    https://www.amazontrust.com/repository/AmazonRootCA3.pem \
    https://www.amazontrust.com/repository/AmazonRootCA4.pem /tmp/amazon-roots/
RUN cat /tmp/amazon-roots/*.pem > /etc/ssl/certs/amazon-root-cas.pem && rm -r /tmp/amazon-roots

# Dependencies from the lockfile, compiled at build time: the image's filesystem is read-only
# at run time (only /tmp is writable), and compiling at init would slow every cold start
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
WORKDIR /var/task
COPY pyproject.toml uv.lock ./
RUN UV_COMPILE_BYTECODE=1 uv sync --frozen --no-dev --no-install-project
ENV PATH="/var/task/.venv/bin:$PATH"
COPY settings/app ./app

# Build metadata last: these values change every build, so the layers above stay cached.
# An empty value would fail settings validation at init; fail the build instead.
ARG VERSION GIT_SHA BUILD_TIME
RUN test -n "$VERSION" && test -n "$GIT_SHA" && test -n "$BUILD_TIME" \
    || { echo "set --build-arg VERSION, GIT_SHA and BUILD_TIME" >&2; exit 1; }
ENV APP__VERSION=$VERSION \
    APP__GIT_SHA=$GIT_SHA \
    APP__BUILD_TIME=$BUILD_TIME

# Starts during the Lambda init phase: importing app.main builds and validates Settings
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8080"]
```

The image carries two extensions in `/opt/extensions`: LWA and the AppConfig agent ([[2f-settings-feature-flags-appconfig]]), whose layer zip must be downloaded before `docker build`. The function itself (`infra/service_stack.py`, shown in [[2b-settings-db-cdk-rotation]]) is a `DockerImageFunction` with a `live` alias, a Function URL on that alias, and a CodeDeploy deployment group that shifts the alias ([[1d-settings-deployments]]).

### Init, invoke, shutdown
| Phase | What runs | Settings consequence |
|---|---|---|
| Init (once per execution environment) | uvicorn imports `app.main`, so `app = create_app()` builds `Settings`; then the lifespan startup creates the DB engine | Validation, AWS reads, engine creation happen here, once |
| Invoke (per request) | LWA forwards the request to uvicorn | `SettingsDep` returns the cached object; no rebuild |
| Shutdown | Lambda sends SIGTERM; uvicorn runs the lifespan shutdown (`engine.dispose()`) | Up to 2 s with an external extension like LWA, then SIGKILL |

- Uvicorn listens only after the import and the lifespan startup succeed, so LWA's readiness check passes only for an app whose settings validated.
- Init is limited to 10 s. Keep it to building settings, a few AWS reads, and creating (not warming) the engine.
- A new execution environment starts per concurrent request, so "once per environment" can still mean many inits at once during a burst.

### Bad config fails init
There is no health check. A version whose settings don't validate never gets past init: uvicorn exits, readiness never passes, and every request routed to it fails with an init error (`INIT_REPORT ... Status: error` or `timeout` in the logs). Lambda retries init on the next request, which fails the same way. CodeDeploy's alarms on the `live` alias roll the version back ([[1d-settings-deployments]]).

### Environment variables
- **4 KB in total**, for all env vars of the function. Keep them to the app's own settings; long lists (`FEATURES__BETA_USERS`) belong in Parameter Store or AppConfig.
- **Readable by anyone with `lambda:GetFunctionConfiguration`**, and frozen into each published version. No secrets in plain env vars in deployed environments: pass the secret's ARN or name, and the app reads the value ([[1a-settings-management]]).
- Lambda has no platform injection of secrets into env vars. The app reads Secrets Manager and Parameter Store itself at init ([[3b-settings-aws-sources-pydantic]]), or per connection for rotated passwords and IAM tokens ([[2b-settings-db-rotated-password]], [[2b-settings-db-iam-auth]]).
- Lambda sets its own variables (`AWS_REGION`, `AWS_LAMBDA_FUNCTION_VERSION`, ...). None match a settings field; keep it that way (see the env var pitfall in [[1a-settings-management]]).

### Reading AWS values at init
Every cold start reads its AWS values again: a burst of 100 new environments is 100 calls to Secrets Manager or Parameter Store. Keep the number of calls per init small (one secret, one parameter path) and give boto3 short timeouts so a slow API fails init quickly instead of eating the 10 s budget.

### Caches live per execution environment
`get_settings()`'s `lru_cache`, the value caches in [[4a-settings-refreshing-values-cache]], and the AppConfig agent's cache ([[2f-settings-feature-flags-appconfig]]) exist once per environment. Environments don't share them, and a TTL counts from that environment's first read. Locks guard nothing across environments; each one handles a single request at a time anyway.

### Database
One request at a time per environment means one connection is enough: `DB__POOL_SIZE=1`, `DB__MAX_OVERFLOW=0`, and `pool_pre_ping` (always on in the engine) to replace connections that died while the environment was frozen. Many environments still mean many connections, so put RDS Proxy in front of the database ([[2b-settings-db-rds-tls]]).

### Files
The image's filesystem is read-only at run time; only `/tmp` is writable (512 MB by default). CA bundles and other files go into the image at build time. File-mounted secrets don't exist on Lambda ([[3a-settings-secret-files]]).

### Function URL and CORS
The Function URL (auth type `NONE`; the app verifies JWTs itself, [[2c-settings-auth]]) sits on the `live` alias. CORS is set in the app only ([[2d-settings-cors]]). A Function URL CORS config would answer preflight requests itself and add duplicate headers to the others, so the stack leaves it unset.

### SnapStart
Not available: SnapStart doesn't support container images. Values read at init are therefore fresh for each new environment.

## Pitfalls
- **Reading settings per request.** Build `Settings` at import, not inside a route or middleware: each request would repeat validation and AWS calls.
- **Treating a 200 from `/healthz` as proof of config.** LWA counts any status below 500 as ready by default; the real check is that the import and lifespan finished. Don't put a DB query in the readiness path: a database blip would then fail every new environment's init.
- **Secrets or `{{resolve:secretsmanager:...}}` in the function's env vars.** Both end up in plain text in the function configuration.
- **Default pool sizes.** 5 + 10 connections per environment, times hundreds of environments, exhausts the database.
- **CORS on both the Function URL and the app.** Browsers reject duplicate `Access-Control-Allow-Origin` headers.

## Related
- [[0-settings-guide]]
- [[1a-settings-management]]
- [[1b-settings-access]]
- [[1d-settings-deployments]]
- [[2b-settings-db]]
- [[2d-settings-cors]]
- [[3b-settings-aws-sources-pydantic]]

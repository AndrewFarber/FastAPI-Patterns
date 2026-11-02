# syntax=docker/dockerfile:1
# Build from examples/ (the lockfile lives there):
#   docker build -f settings/Dockerfile --build-arg VERSION=... --build-arg GIT_SHA=... --build-arg BUILD_TIME=... .
# Images are pinned by digest: a tag can be moved to a different image. The tag stays for
# readers and update tools (Renovate, Dependabot), which bump tag and digest together.
FROM public.ecr.aws/docker/library/python:3.14-slim@sha256:930e1abba7c4e8f96ed93e8012c35d174d7732752731bbd5e8e757d7ec6f3966

# Lambda Web Adapter: a Lambda extension that starts with the container, waits until
# the readiness path answers, then turns each invocation into an HTTP request to uvicorn
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0@sha256:17cfd08eff1dfea3f6a9a1e9c65fdac80aa4919b6085e746615530f43f57d2f1 /lambda-adapter /opt/extensions/lambda-adapter
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
COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /usr/local/bin/uv
WORKDIR /var/task
COPY pyproject.toml uv.lock ./
RUN UV_COMPILE_BYTECODE=1 uv sync --frozen --no-dev --no-install-project
ENV PATH="/var/task/.venv/bin:$PATH"
COPY settings/app ./app
RUN python -m compileall -q app   # the app's own modules too: uv sync compiled only the dependencies

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

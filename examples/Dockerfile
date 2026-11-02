# syntax=docker/dockerfile:1
# Build from examples/ (the lockfile lives there):
#   docker build .
# Images are pinned by digest: a tag can be moved to a different image. The tag stays for
# readers and update tools (Renovate, Dependabot), which bump tag and digest together.
FROM public.ecr.aws/docker/library/python:3.14-slim@sha256:930e1abba7c4e8f96ed93e8012c35d174d7732752731bbd5e8e757d7ec6f3966
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# CA bundle for DB__SSLROOTCERT: the RDS global bundle. Files added from a URL are
# mode 600, so make it readable by the non-root user the app runs as.
ADD --chmod=644 https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem /etc/ssl/certs/rds-global-bundle.pem

# Dependencies from the lockfile, compiled at build time so startup doesn't compile them
COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN UV_COMPILE_BYTECODE=1 uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH"
COPY app ./app
RUN python -m compileall -q app   # the app's own modules too: uv sync compiled only the dependencies

USER nobody
# Importing app.main builds and validates Settings: bad config fails startup
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

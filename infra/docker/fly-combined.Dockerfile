# Single-image Fly.io deploy: API + worker in one container.
# Used by fly.api.toml for the SQLite-backed alpha path.
# The Docker-compose "two containers" layout still lives in api.Dockerfile +
# worker.Dockerfile and is unchanged.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /repo

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY infra/docker/entrypoint-combined.sh /entrypoint.sh

RUN pip install --upgrade pip setuptools wheel && \
    pip install -e ".[dev]" && \
    chmod +x /entrypoint.sh

ENV PYTHONPATH=/repo/packages/shared:/repo/apps/api:/repo/apps/worker

EXPOSE 8000

CMD ["/entrypoint.sh"]

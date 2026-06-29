# Container image for the festers service - the unit that ships to the box.
# Built with uv for reproducible resolution from uv.lock. CI builds and pushes
# this to ghcr on every merge to main (see .github/workflows/release.yml).
FROM python:3.12-slim AS base

# uv: copy the static binary from the official image (no curl/install step).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies first (cached layer), without dev deps.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Then the app itself. data/festivals/<id>/schedule.json files are the source of
# truth and are baked in; data/plans + data/auth are runtime state from volumes.
COPY festers ./festers
COPY data ./data
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uvicorn", "festers.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.14-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

FROM base AS builder

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --no-install-project --extra k8s

COPY README.md ./
COPY src ./src

RUN uv sync --no-dev --no-editable --extra k8s

FROM python:3.14-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

RUN useradd --create-home --uid 10001 house

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER 10001

EXPOSE 7777

CMD ["auction-house"]
 ADD source destFROM python:3.12-slim

#installs uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /project

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 2. copy all your code
COPY src/ src/

ENV PATH="/project/.venv/bin:$PATH" \
    PYTHONPATH=/project/src

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
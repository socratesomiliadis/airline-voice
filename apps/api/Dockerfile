FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/contracts/ packages/contracts/
COPY apps/api/ apps/api/
COPY data/flights/ data/flights/
COPY knowledge/ knowledge/
COPY apps/refiner/pyproject.toml apps/refiner/pyproject.toml
RUN uv sync --frozen --no-dev --package airline-api --no-editable \
    && useradd --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "airline_api.main:app", "--host", "0.0.0.0", "--port", "8000"]

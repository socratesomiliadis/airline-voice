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
COPY apps/refiner/ apps/refiner/
COPY apps/api/pyproject.toml apps/api/pyproject.toml
RUN uv sync --frozen --no-dev --package airline-refiner --no-editable \
    && useradd --create-home app \
    && mkdir /app/artifacts \
    && chown app:app /app/artifacts
USER app
ENTRYPOINT ["airline-refiner"]
CMD ["--help"]

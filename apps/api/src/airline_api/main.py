"""ASGI entry point. Construction performs no database or provider network calls."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from airline_api.api.router import router
from airline_api.core.config import Settings
from airline_api.core.logging import configure_logging
from airline_api.infrastructure.database.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        database = Database(settings.database_url.get_secret_value())
        app.state.database = database
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(
        title="Airline Voice API",
        version="0.1.0",
        description="Scaffold only. Feature endpoints return 501 until implemented.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.include_router(router)
    return app


app = create_app()

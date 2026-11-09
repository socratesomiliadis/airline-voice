"""ASGI entry point. Construction performs no database or provider network calls."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from airline_api.api.router import router
from airline_api.core.config import Settings
from airline_api.core.logging import configure_logging
from airline_api.infrastructure.database.session import Database
from airline_api.modules.bookings.errors import BookingError
from airline_api.modules.bookings.policies import PolicyCatalog
from airline_api.modules.monitoring.store import ObservationStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level)
        database = Database(settings.database_url.get_secret_value())
        app.state.database = database
        try:
            app.state.policies = PolicyCatalog.from_directory(settings.knowledge_dir)
            yield
        finally:
            await database.dispose()

    app = FastAPI(
        title="Airline Voice API",
        version="0.1.0",
        description=(
            "Persistent fictional airline bookings and ElevenLabs webhook tools. "
            "Read-only observation of autonomous refinement runs."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.observation_store = ObservationStore(settings.refiner_artifacts_dir)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Agent-Api-Key"],
    )
    app.include_router(router)

    @app.exception_handler(BookingError)
    async def booking_error_handler(request: Request, exc: BookingError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    return app


app = create_app()

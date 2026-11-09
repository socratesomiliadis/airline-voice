"""Root route composition; all feature routes are versioned."""

from fastapi import APIRouter

from airline_api.api.health import router as health_router
from airline_api.modules.bookings.flights_router import router as flights_router
from airline_api.modules.bookings.router import router as bookings_router
from airline_api.modules.monitoring.router import router as monitoring_router
from airline_api.modules.voice.router import router as voice_router

router = APIRouter()
router.include_router(health_router)

v1 = APIRouter(prefix="/api/v1")
v1.include_router(bookings_router)
v1.include_router(flights_router)
v1.include_router(monitoring_router)
v1.include_router(voice_router)
router.include_router(v1)

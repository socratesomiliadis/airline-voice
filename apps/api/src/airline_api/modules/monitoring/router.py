"""Reserved monitoring endpoints; no handlers perform work."""

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get(
    "/events",
    status_code=501,
    response_model=None,
    summary="Stream monitoring events (transport deferred)",
)
async def stream_events() -> None:
    not_implemented("monitoring.stream_events")

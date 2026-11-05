"""Reserved support endpoints; no handlers perform work."""

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/requests", tags=["support"])


@router.post("", status_code=501, response_model=None, summary="Submit a customer request")
async def create_request() -> None:
    not_implemented("support.create_request")

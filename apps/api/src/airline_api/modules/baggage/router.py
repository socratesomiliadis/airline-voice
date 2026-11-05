"""Reserved baggage endpoints; no handlers perform work."""

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/baggage", tags=["baggage"])


@router.post("/inquiries", status_code=501, response_model=None, summary="Submit a baggage inquiry")
async def create_inquiry() -> None:
    not_implemented("baggage.create_inquiry")

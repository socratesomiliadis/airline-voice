"""Reserved knowledge endpoints; no handlers perform work."""

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/documents", status_code=501, response_model=None, summary="List knowledge documents")
async def list_documents() -> None:
    not_implemented("knowledge.list_documents")


@router.post(
    "/documents", status_code=501, response_model=None, summary="Ingest a knowledge document"
)
async def ingest_document() -> None:
    not_implemented("knowledge.ingest_document")


@router.post("/search", status_code=501, response_model=None, summary="Search knowledge")
async def search_knowledge() -> None:
    not_implemented("knowledge.search_knowledge")

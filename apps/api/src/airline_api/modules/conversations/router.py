"""Reserved conversations endpoints; no handlers perform work."""

from uuid import UUID

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", status_code=501, response_model=None, summary="List conversations")
async def list_conversations() -> None:
    not_implemented("conversations.list_conversations")


@router.get(
    "/{conversation_id}", status_code=501, response_model=None, summary="Get a conversation"
)
async def get_conversation(conversation_id: UUID) -> None:
    not_implemented("conversations.get_conversation")

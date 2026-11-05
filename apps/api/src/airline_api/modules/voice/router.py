"""Reserved voice endpoints; no handlers perform work."""

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/sessions", status_code=501, response_model=None, summary="Create a voice session")
async def create_session() -> None:
    not_implemented("voice.create_session")


@router.post(
    "/webhooks/elevenlabs",
    status_code=501,
    response_model=None,
    summary="Receive an ElevenLabs webhook",
)
async def receive_webhook() -> None:
    not_implemented("voice.receive_webhook")

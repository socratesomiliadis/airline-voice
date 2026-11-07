"""Authenticated, observation-only snapshots and reconnectable server-sent events."""

import asyncio
import hashlib
from collections.abc import AsyncIterator
from typing import Annotated

from airline_contracts.monitoring import MonitoringSnapshot
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from airline_api.core.auth import require_agent_key
from airline_api.modules.monitoring.store import RUN_ID_PATTERN, ObservationStore

router = APIRouter(
    prefix="/monitoring", tags=["monitoring"], dependencies=[Depends(require_agent_key)]
)
type RunSelection = Annotated[str | None, Query(pattern=RUN_ID_PATTERN)]


async def snapshot(store: ObservationStore, run_id: str | None) -> MonitoringSnapshot:
    try:
        return await asyncio.to_thread(store.snapshot, run_id)
    except FileNotFoundError:
        raise HTTPException(404, detail={"code": "run_not_found"}) from None


@router.get("/snapshot", response_model=MonitoringSnapshot)
async def get_snapshot(request: Request, run_id: RunSelection = None) -> MonitoringSnapshot:
    return await snapshot(request.app.state.observation_store, run_id)


async def observation_events(
    store: ObservationStore,
    request: Request,
    run_id: str | None,
) -> AsyncIterator[str]:
    previous = ""
    heartbeat = asyncio.get_running_loop().time()
    yield "retry: 2000\n\n"
    while not await request.is_disconnected():
        try:
            payload = (await snapshot(store, run_id)).model_dump_json()
            revision = hashlib.sha256(payload.encode()).hexdigest()[:20]
            if revision != previous:
                # Full snapshots make reconnect idempotent: no dropped messages or duplicate turns.
                yield f"id: {revision}\nevent: snapshot\ndata: {payload}\n\n"
                previous = revision
            if asyncio.get_running_loop().time() - heartbeat >= 10:
                yield "event: heartbeat\ndata: {}\n\n"
                heartbeat = asyncio.get_running_loop().time()
        except HTTPException:
            yield 'event: unavailable\ndata: {"code":"run_not_found"}\n\n'
            return
        await asyncio.sleep(0.5)


@router.get("/events", summary="Observe live refinement updates")
async def stream_events(request: Request, run_id: RunSelection = None) -> StreamingResponse:
    store: ObservationStore = request.app.state.observation_store
    await snapshot(store, run_id)
    return StreamingResponse(
        observation_events(store, request, run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )

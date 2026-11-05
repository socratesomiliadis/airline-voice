"""Reserved refinement endpoints; no handlers perform work."""

from fastapi import APIRouter

from airline_api.core.placeholders import not_implemented

router = APIRouter(prefix="/refinement", tags=["refinement"])


@router.post("/runs", status_code=501, response_model=None, summary="Start a refinement run")
async def start_run() -> None:
    not_implemented("refinement.start_run")


@router.get(
    "/iterations", status_code=501, response_model=None, summary="List refinement iterations"
)
async def list_iterations() -> None:
    not_implemented("refinement.list_iterations")


@router.get("/evaluations", status_code=501, response_model=None, summary="List evaluations")
async def list_evaluations() -> None:
    not_implemented("refinement.list_evaluations")


@router.get(
    "/changes", status_code=501, response_model=None, summary="List proposed or applied changes"
)
async def list_changes() -> None:
    not_implemented("refinement.list_changes")

"""HTTP route for the `get_run_history` query slice.

`GET /runs/{run_id}/history` returns 200 + RunHistoryResponse on hit, 404
on miss. Unlike `get_run`'s route, there is no capture path / experiment
identity to destructure here by design -- see `handler.py`'s module
docstring for why those two vaults are deliberately never touched.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.run.features.get_run_history.handler import Handler
from cora.run.features.get_run_history.query import GetRunHistory


class RunHistoryEventItem(BaseModel):
    """One event off the run's own stream, primitives only."""

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]


class RunHistoryObservationItem(BaseModel):
    """One observation-trail row, primitives only."""

    event_id: UUID
    channel_name: str
    value: float | None
    categorical_value: str | None
    units: str | None
    sampling_procedure: str
    sampled_at: datetime
    occurred_at: datetime
    recorded_at: datetime
    is_simulated: bool


class RunHistoryResponse(BaseModel):
    """Read-side DTO at the API boundary for one run's full history."""

    run_id: UUID
    name: str
    status: str
    events: list[RunHistoryEventItem]
    observations: list[RunHistoryObservationItem]
    observations_truncated: bool


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.run.get_run_history
    return handler


router = APIRouter(tags=["run"])


@router.get(
    "/runs/{run_id}/history",
    status_code=status.HTTP_200_OK,
    response_model=RunHistoryResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No run exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a run's full exact-timestamped history",
)
async def get_run_history_route(
    run_id: Annotated[UUID, Path(description="Target run's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> RunHistoryResponse:
    view = await handler(
        GetRunHistory(run_id=run_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found",
        )
    return RunHistoryResponse(
        run_id=view.run_id,
        name=view.name,
        status=view.status,
        events=[
            RunHistoryEventItem(
                event_id=e.event_id,
                event_type=e.event_type,
                version=e.version,
                occurred_at=e.occurred_at,
                recorded_at=e.recorded_at,
                payload=e.payload,
            )
            for e in view.events
        ],
        observations=[
            RunHistoryObservationItem(
                event_id=o.event_id,
                channel_name=o.channel_name,
                value=o.value,
                categorical_value=o.categorical_value,
                units=o.units,
                sampling_procedure=o.sampling_procedure,
                sampled_at=o.sampled_at,
                occurred_at=o.occurred_at,
                recorded_at=o.recorded_at,
                is_simulated=o.is_simulated,
            )
            for o in view.observations
        ],
        observations_truncated=view.observations_truncated,
    )

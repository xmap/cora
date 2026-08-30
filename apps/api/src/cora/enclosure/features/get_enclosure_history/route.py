"""HTTP route for the `get_enclosure_history` query slice.

`GET /enclosures/{enclosure_id}/history` returns 200 + EnclosureHistoryResponse
on hit, 404 on miss.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel

from cora.enclosure.features.get_enclosure_history.handler import Handler
from cora.enclosure.features.get_enclosure_history.query import GetEnclosureHistory
from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)


class EnclosureHistoryEventItem(BaseModel):
    """One event off the enclosure's own stream, primitives only."""

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]


class EnclosureHistoryResponse(BaseModel):
    """Read-side DTO at the API boundary for one enclosure's full history."""

    enclosure_id: UUID
    name: str
    permit_status: str
    lifecycle: str
    events: list[EnclosureHistoryEventItem]
    events_truncated: bool


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.enclosure.get_enclosure_history
    return handler


router = APIRouter(tags=["enclosure"])


@router.get(
    "/enclosures/{enclosure_id}/history",
    status_code=status.HTTP_200_OK,
    response_model=EnclosureHistoryResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No enclosure exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get an enclosure's full exact-timestamped history",
)
async def get_enclosure_history_route(
    enclosure_id: Annotated[UUID, Path(description="Target enclosure's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> EnclosureHistoryResponse:
    view = await handler(
        GetEnclosureHistory(enclosure_id=enclosure_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Enclosure {enclosure_id} not found",
        )
    return EnclosureHistoryResponse(
        enclosure_id=view.enclosure_id,
        name=view.name,
        permit_status=view.permit_status,
        lifecycle=view.lifecycle,
        events=[
            EnclosureHistoryEventItem(
                event_id=e.event_id,
                event_type=e.event_type,
                version=e.version,
                occurred_at=e.occurred_at,
                recorded_at=e.recorded_at,
                payload=e.payload,
            )
            for e in view.events
        ],
        events_truncated=view.events_truncated,
    )

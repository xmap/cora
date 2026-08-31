"""HTTP route for the `define_surface` slice."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.trust.aggregates.surface import SURFACE_NAME_MAX_LENGTH, SurfaceKind
from cora.trust.features.define_surface.command import DefineSurface
from cora.trust.features.define_surface.handler import IdempotentHandler


class DefineSurfaceRequest(BaseModel):
    """Body for `POST /surfaces`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=SURFACE_NAME_MAX_LENGTH,
        description="Display name for the new surface.",
    )
    kind: SurfaceKind = Field(
        ...,
        description=(
            "Process-level arrival kind. Closed enum; one of "
            "http / mcp_stdio / mcp_streamable_http / in_process."
        ),
    )


class DefineSurfaceResponse(BaseModel):
    """Response body for `POST /surfaces`."""

    surface_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.trust.define_surface
    return handler


router = APIRouter(tags=["trust"])


@router.post(
    "/surfaces",
    status_code=status.HTTP_201_CREATED,
    response_model=DefineSurfaceResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only name).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (unknown kind, oversized name, etc.) "
                "OR Idempotency-Key was reused with a different request body."
            ),
        },
    },
    summary="Define a new arrival Surface",
)
async def post_surfaces(
    body: DefineSurfaceRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description="Optional Idempotency-Key for safe retry semantics.",
        ),
    ] = None,
) -> DefineSurfaceResponse:
    surface_id = await handler(
        DefineSurface(name=body.name, kind=body.kind),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return DefineSurfaceResponse(surface_id=surface_id)

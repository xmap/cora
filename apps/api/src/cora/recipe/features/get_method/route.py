"""HTTP route for the `get_method` query slice.

`GET /methods/{method_id}` returns 200 + MethodResponse on hit, 404
on miss. The handler returns `MethodView | None`; the route maps
None to 404 via HTTPException (idiomatic in routes; the BC's
exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).

`needed_family_ids` serializes as a list of UUIDs in the response
(JSON arrays don't have set semantics). The list is sorted by
string form for determinism — same logical family set, same
response bytes (helps test reproducibility and any future ETag-
style caching).

`created_at` / `versioned_at` / `deprecated_at` are sourced from the
`proj_recipe_method_summary` projection, not from aggregate state
(Path C). All three may be null: `created_at`
when the projection hasn't caught up after a recent define;
`versioned_at` until the first version_method; `deprecated_at` until
deprecation. Operators should treat any null while `status` is
already past the corresponding transition as a transient eventual-
consistency window.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.recipe.aggregates.method import METHOD_NAME_MAX_LENGTH
from cora.recipe.features.get_method.handler import Handler
from cora.recipe.features.get_method.query import GetMethod


class MethodResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `needed_family_ids` is sorted by UUID string form.
    `needed_supplies` is sorted lexically by kind string;
    Supply.kind values (NOT instance UUIDs).
    `status` is the StrEnum's string value (Defined / Versioned /
    Deprecated). `version` is the operator-supplied label of the most
    recent version_method call (null until first version).
    `created_at` / `versioned_at` / `deprecated_at` are projection-
    sourced lifecycle timestamps (Path C). Null
    semantics under eventual consistency: read together with `status`.
    If `status >= Defined` but `created_at` is null, the projection
    has not yet folded `MethodDefined` (transient lag). If
    `status == Versioned` but `versioned_at` is null, the projection
    has not yet folded the latest `MethodVersioned`. If
    `status == Deprecated` but `deprecated_at` is null, the projection
    has not yet folded `MethodDeprecated`. A 404 means the Method
    aggregate itself does not exist (fold-on-read miss); a 200 with
    null timestamps always means projection lag, never a missing
    transition.
    """

    id: UUID
    name: str = Field(..., max_length=METHOD_NAME_MAX_LENGTH)
    needed_family_ids: list[UUID]
    needed_supplies: list[str]
    status: str
    version: str | None
    # compute classification, read from folded state. execution_pattern
    # is the enum string value (Batch / Iterative / Streaming) or null
    # for unclassified (legacy / acquisition) Methods; the two claims
    # default False. Rendered as a primitive string to match `status`.
    execution_pattern: str | None
    monotone_quality: bool
    resumable_from_checkpoint: bool
    created_at: datetime | None = None
    versioned_at: datetime | None = None
    deprecated_at: datetime | None = None


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.recipe.get_method
    return handler


router = APIRouter(tags=["recipe"])


@router.get(
    "/methods/{method_id}",
    status_code=status.HTTP_200_OK,
    response_model=MethodResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No method exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a method by id",
)
async def get_methods(
    method_id: Annotated[UUID, Path(description="Target method's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> MethodResponse:
    view = await handler(
        GetMethod(method_id=method_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if view is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Method {method_id} not found",
        )
    method = view.method
    timestamps = view.timestamps
    return MethodResponse(
        id=method.id,
        name=method.name.value,
        needed_family_ids=sorted(method.needed_family_ids, key=str),
        needed_supplies=sorted(method.needed_supplies),
        status=method.status.value,
        version=method.version,
        execution_pattern=(
            method.execution_pattern.value if method.execution_pattern is not None else None
        ),
        monotone_quality=method.monotone_quality,
        resumable_from_checkpoint=method.resumable_from_checkpoint,
        created_at=timestamps.created_at if timestamps is not None else None,
        versioned_at=timestamps.versioned_at if timestamps is not None else None,
        deprecated_at=timestamps.deprecated_at if timestamps is not None else None,
    )

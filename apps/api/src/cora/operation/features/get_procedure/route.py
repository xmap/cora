"""HTTP route for the `get_procedure` query slice.

`GET /procedures/{procedure_id}` returns 200 + ProcedureResponse on
hit, 404 on miss. The handler returns `Procedure | None`; the route
maps None to 404 via HTTPException (idiomatic in routes; the BC's
exception-handler infrastructure stays focused on domain /
application errors raised deeper in the stack).

`target_asset_ids` serializes as a sorted list of UUIDs in the
response (JSON arrays don't have set semantics). Sorted by string
form for determinism -- same logical Asset set, same response bytes
(helps test reproducibility and any future ETag-style caching).
"""

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
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
    ProcedureStatus,
)
from cora.operation.features.get_procedure.handler import Handler
from cora.operation.features.get_procedure.query import GetProcedure


class ProcedureResponse(BaseModel):
    """Read-side DTO at the API boundary.

    Carries primitives, not domain VOs. Decouples the wire format
    from the domain model so the two can evolve independently.
    `target_asset_ids` is sorted by UUID string form. `status` is the
    StrEnum's string value (Defined / Running / Completed / Aborted /
    Truncated). `parent_run_id` is null for standalone procedures.
    """

    id: UUID
    name: str = Field(..., max_length=PROCEDURE_NAME_MAX_LENGTH)
    kind: str = Field(..., max_length=PROCEDURE_KIND_MAX_LENGTH)
    target_asset_ids: list[UUID]
    status: ProcedureStatus
    parent_run_id: UUID | None
    current_iteration_index: int | None = None
    iteration_count: int = 0


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.get_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.get(
    "/procedures/{procedure_id}",
    status_code=status.HTTP_200_OK,
    response_model=ProcedureResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ErrorResponse,
            "description": "No procedure exists with the given id.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Path parameter failed schema validation.",
        },
    },
    summary="Get a procedure by id",
)
async def get_procedures(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ProcedureResponse:
    procedure = await handler(
        GetProcedure(procedure_id=procedure_id),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    if procedure is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Procedure {procedure_id} not found",
        )
    return ProcedureResponse(
        id=procedure.id,
        name=procedure.name.value,
        kind=procedure.kind,
        target_asset_ids=sorted(procedure.target_asset_ids, key=str),
        status=procedure.status,
        parent_run_id=procedure.parent_run_id,
        current_iteration_index=procedure.current_iteration_index,
        iteration_count=procedure.iteration_count,
    )

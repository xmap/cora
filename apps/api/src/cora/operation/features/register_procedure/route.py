"""HTTP route for the `register_procedure` slice.

Pydantic request/response schemas + APIRouter for `POST /procedures`.
The slice's BC-level wiring
(`cora.operation.routes.register_operation_routes`) includes this
router on the FastAPI app.

`target_asset_ids` accepts a list of UUIDs at the API boundary
(JSON arrays don't have set semantics); the handler converts to
frozenset before threading into the command. Empty list is allowed
(maps to empty frozenset, valid for facility-envelope procedures
that don't act on a specific Asset).
"""

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
from cora.operation.aggregates.procedure import (
    PROCEDURE_KIND_MAX_LENGTH,
    PROCEDURE_NAME_MAX_LENGTH,
)
from cora.operation.features.register_procedure.command import RegisterProcedure
from cora.operation.features.register_procedure.handler import IdempotentHandler


class RegisterProcedureRequest(BaseModel):
    """Body for `POST /procedures`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=PROCEDURE_NAME_MAX_LENGTH,
        description=(
            "Operator-readable display name for the procedure (for example "
            "'2-BM rotation-axis alignment 2026-05-15', 'Vessel-A bakeout')."
        ),
    )
    kind: str = Field(
        ...,
        min_length=1,
        max_length=PROCEDURE_KIND_MAX_LENGTH,
        description=(
            "Free-form ISA-106 procedure-kind discriminator (bakeout, "
            "alignment, characterization, recovery, beam_mode_change, "
            "id_maintenance, kb_switching, etc.). Documented starter "
            "vocabulary in project_operation_design memo; closed StrEnum "
            "promotion deferred until pilot vocabulary settles."
        ),
    )
    target_asset_ids: list[UUID] = Field(
        default_factory=list[UUID],
        description=(
            "Asset ids this procedure acts on. May be empty (valid for "
            "facility-envelope procedures like beam-mode change that "
            "don't act on a specific Asset). Eventual-consistency: ids "
            "are NOT verified at register time; gating happens at "
            "start_procedure (10c-b) via ProcedureStartContext."
        ),
    )
    parent_run_id: UUID | None = Field(
        default=None,
        description=(
            "Optional parent Run binding. None = standalone procedure "
            "(bakeout, characterization run between Runs). Set = "
            "Phase-of-Run procedure (alignment invoked mid-Run; "
            "resolves the Phase aggregate question per "
            "project_operation_design memo)."
        ),
    )
    capability_id: UUID | None = Field(
        default=None,
        description=(
            "Optional cross-BC binding to the universal Capability "
            "template (Recipe BC 6k) this Procedure realizes as a "
            "Procedure-shaped executor. None for ceremony Procedures "
            "with no matching template. When supplied, the bound "
            "Capability must declare `Procedure` in its executor_shapes "
            "set; otherwise 409. Eventual-consistency: the Capability "
            "stream is loaded at handler time, not API-boundary time. "
            "Same additive shape as Method.capability_id (6l-additive)."
        ),
    )
    max_consecutive_unconverged_iterations: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Optional 'patience' cap for an iterative Procedure: the max "
            "number of consecutive iterations that may end NOT converged "
            "before start_iteration refuses the next one (409). The streak "
            "resets on a converged iteration. None = no cap. Never "
            "auto-aborts; the operator completes or aborts when blocked."
        ),
    )


class RegisterProcedureResponse(BaseModel):
    """Response body for `POST /procedures`."""

    procedure_id: UUID


def _get_handler(request: Request) -> IdempotentHandler:
    handler: IdempotentHandler = request.app.state.operation.register_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterProcedureResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Domain invariant violated (for example whitespace-only name or kind).",
        },
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": (
                "Defensive guard: the target procedure stream already has events. "
                "Essentially impossible in production with UUIDv7 ids; documented "
                "for OpenAPI completeness against the BC's exception handler."
            ),
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation (missing field, "
                "length out of bounds, malformed UUID), OR Idempotency-Key "
                "was reused with a different request body."
            ),
        },
    },
    summary="Register a new episodic operational procedure (lands in Defined)",
)
async def post_procedures(
    body: RegisterProcedureRequest,
    handler: Annotated[IdempotentHandler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
    idempotency_key: Annotated[
        str | None,
        Header(
            alias="Idempotency-Key",
            description=(
                "Optional client-supplied unique key per logical request. "
                "Retries with the same key + same body return the cached "
                "response instead of re-creating the procedure."
            ),
        ),
    ] = None,
) -> RegisterProcedureResponse:
    procedure_id = await handler(
        RegisterProcedure(
            name=body.name,
            kind=body.kind,
            target_asset_ids=frozenset(body.target_asset_ids),
            parent_run_id=body.parent_run_id,
            capability_id=body.capability_id,
            max_consecutive_unconverged_iterations=body.max_consecutive_unconverged_iterations,
        ),
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
        idempotency_key=idempotency_key,
    )
    return RegisterProcedureResponse(procedure_id=procedure_id)

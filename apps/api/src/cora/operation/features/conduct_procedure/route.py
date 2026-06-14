"""HTTP route for the `conduct_procedure` slice.

`POST /procedures/{procedure_id}/conduct` accepts a JSON body carrying
the step list the Conductor walks. Returns 200 OK with a
`ConductProcedureResponse` body summarising the outcome (procedure_id +
completed_count + succeeded + optional failure detail).

## Response code: always 200, failures in body

`ConductProcedure` is an orchestration endpoint, not a CRUD call.
Step-level failures (a setpoint write that the IOC rejected, a
check that did not pass, an action body that raised) are NORMAL
operational outcomes that the operator needs to triage. They land
in the response body as a structured failure summary, not as HTTP
4xx / 5xx. This mirrors how CI / build-runner APIs report job
results: a failed run is a 200 OK carrying a failed status.

Only true protocol / auth / validation faults map to HTTP error
codes (422 for malformed JSON, 403 for authz deny). Everything
downstream of "authorized request with valid body" is captured in
the result body so a single client code-path covers every outcome
without parsing HTTP status codes.

## Pydantic wire types

The Conductor's `Step = SetpointStep | ActionStep | CheckStep` and
`CheckCriterion = EqualsCriterion | WithinToleranceCriterion` discriminated unions
land on the wire as JSON discriminated unions with a `kind` field.
Pydantic's `Field(discriminator="kind")` validates the union at
parse time so a malformed step kind fails the request with a 422
before the handler ever runs.

Per-step `value` and `criterion.expected` are typed broadly
(`int | float | bool | str | list[Any]`) to match the
ControlPort's value vocabulary. Tuples-on-the-wire arrive as lists;
the converter widens to tuple for the in-process Conductor.
"""

from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, status
from pydantic import BaseModel, Field

from cora.infrastructure.routing import (
    ErrorResponse,
    get_correlation_id,
    get_principal_id,
    get_surface_id,
)
from cora.operation.conductor import (
    ActionStep,
    CheckCriterion,
    CheckStep,
    ConductorFailure,
    EqualsCriterion,
    SetpointStep,
    Step,
    WithinToleranceCriterion,
)
from cora.operation.features.conduct_procedure.command import (
    ConductProcedure,
    ConductProcedureResult,
)
from cora.operation.features.conduct_procedure.handler import Handler

_STEP_BATCH_MAX = 500
"""Mirror of `append_activities`'s batch cap. A single
`ConductProcedure` request never carries more than this many steps;
larger procedures split client-side via multiple sequential runs."""


class _SetpointStepRequest(BaseModel):
    """JSON wire shape for a `SetpointStep`."""

    kind: Literal["setpoint"]
    address: str = Field(..., min_length=1)
    value: int | float | bool | str | list[Any]
    verify: bool = False

    model_config = {"extra": "forbid"}


class _ActionStepRequest(BaseModel):
    """JSON wire shape for an `ActionStep`."""

    kind: Literal["action"]
    name: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class _EqualsCriterion(BaseModel):
    """JSON wire shape for an `EqualsCriterion`."""

    kind: Literal["equals"]
    expected: int | float | bool | str | list[Any]

    model_config = {"extra": "forbid"}


class _WithinToleranceCriterion(BaseModel):
    """JSON wire shape for a `WithinToleranceCriterion`."""

    kind: Literal["within_tolerance"]
    expected: float
    tolerance: float = Field(..., ge=0.0)

    model_config = {"extra": "forbid"}


_CriterionRequest = Annotated[
    _EqualsCriterion | _WithinToleranceCriterion,
    Field(discriminator="kind"),
]


class _CheckStepRequest(BaseModel):
    """JSON wire shape for a `CheckStep`."""

    kind: Literal["check"]
    address: str = Field(..., min_length=1)
    criterion: _CriterionRequest

    model_config = {"extra": "forbid"}


_StepRequest = Annotated[
    _SetpointStepRequest | _ActionStepRequest | _CheckStepRequest,
    Field(discriminator="kind"),
]


class ConductProcedureRequest(BaseModel):
    """Body for `POST /procedures/{procedure_id}/conduct`."""

    steps: list[_StepRequest] = Field(
        default_factory=list[_StepRequest],
        max_length=_STEP_BATCH_MAX,
        description=(
            f"Steps the Conductor walks in order (0-{_STEP_BATCH_MAX}). "
            "Empty list is valid: start + complete fire with no steps."
        ),
    )

    model_config = {"extra": "forbid"}


class _ConductorFailureResponse(BaseModel):
    """JSON wire shape for `ConductorFailure`."""

    step_index: int | None
    source_kind: str
    target: str
    error_class: str
    message: str


class ConductProcedureResponse(BaseModel):
    """Response body for the conduct_procedure slice.

    `succeeded` is the canonical pass/fail bit; `failure` is non-null
    iff `succeeded` is False. `completed_count` is informational
    (the number of steps that ran successfully before halt, if any).

    `actuation_kind` is the raw `ActuationKind` value (Physical /
    Simulated / Hybrid) the Conductor observed, or None when nothing
    instrumented was actuated. Read-only operator visibility; the gate
    that consumes it reads the value server-side off the Procedure
    stream, never back from this response.
    """

    procedure_id: UUID
    completed_count: int
    succeeded: bool
    failure: _ConductorFailureResponse | None = None
    actuation_kind: str | None = None


def criterion_from_wire(
    wire: _EqualsCriterion | _WithinToleranceCriterion,
) -> CheckCriterion:
    """Build a Conductor `CheckCriterion` from a Pydantic wire model.

    Public because `tool.py` calls it too (MCP + REST share the same
    wire schema; the converter is the seam between the JSON shape
    and the in-process Conductor type).
    """
    if isinstance(wire, _EqualsCriterion):
        expected: Any = wire.expected
        if isinstance(expected, list):
            # wire.expected is a JSON list of Any; tuple-coerce for the in-process EqualsCriterion
            return EqualsCriterion(expected=cast("tuple[Any, ...]", tuple(expected)))  # pyright: ignore[reportUnknownArgumentType]
        return EqualsCriterion(expected=expected)
    return WithinToleranceCriterion(expected=wire.expected, tolerance=wire.tolerance)


def step_from_wire(
    wire: _SetpointStepRequest | _ActionStepRequest | _CheckStepRequest,
) -> Step:
    """Build a Conductor `Step` from a Pydantic wire model.

    Public because `tool.py` calls it too (MCP + REST share the same
    wire schema).
    """
    if isinstance(wire, _SetpointStepRequest):
        value: Any = wire.value
        if isinstance(value, list):
            return SetpointStep(
                address=wire.address,
                value=cast("tuple[Any, ...]", tuple(value)),  # pyright: ignore[reportUnknownArgumentType]
                verify=wire.verify,
            )
        return SetpointStep(address=wire.address, value=value, verify=wire.verify)
    if isinstance(wire, _ActionStepRequest):
        return ActionStep(name=wire.name, params=wire.params)
    return CheckStep(
        address=wire.address,
        criterion=criterion_from_wire(wire.criterion),
    )


def _failure_to_wire(failure: ConductorFailure) -> _ConductorFailureResponse:
    return _ConductorFailureResponse(
        step_index=failure.step_index,
        source_kind=failure.source_kind,
        target=failure.target,
        error_class=failure.error_class,
        message=failure.message,
    )


def result_to_wire(result: ConductProcedureResult) -> ConductProcedureResponse:
    """Build a `ConductProcedureResponse` from the slice's `ConductProcedureResult`.

    Public because `tool.py` calls it too.
    """
    return ConductProcedureResponse(
        procedure_id=result.procedure_id,
        completed_count=result.completed_count,
        succeeded=result.succeeded,
        failure=_failure_to_wire(result.failure) if result.failure is not None else None,
        actuation_kind=result.actuation_kind,
    )


def _get_handler(request: Request) -> Handler:
    handler: Handler = request.app.state.operation.conduct_procedure
    return handler


router = APIRouter(tags=["operation"])


@router.post(
    "/procedures/{procedure_id}/conduct",
    status_code=status.HTTP_200_OK,
    response_model=ConductProcedureResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "model": ErrorResponse,
            "description": "Authorize port denied the command.",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": (
                "Request body failed schema validation: unknown step "
                "kind, missing required field, batch over cap, invalid "
                "criterion shape."
            ),
        },
    },
    summary=(
        "Conduct a Procedure: start -> walk steps via ControlPort + actions + "
        "checks -> complete (success) or abort (failure)."
    ),
)
async def post_procedures_conduct(
    procedure_id: Annotated[UUID, Path(description="Target procedure's id.")],
    body: ConductProcedureRequest,
    handler: Annotated[Handler, Depends(_get_handler)],
    cid: Annotated[UUID, Depends(get_correlation_id)],
    principal_id: Annotated[UUID, Depends(get_principal_id)],
    surface_id: Annotated[UUID, Depends(get_surface_id)],
) -> ConductProcedureResponse:
    """Conduct a Procedure end-to-end. Failures land in the response body."""
    command = ConductProcedure(
        procedure_id=procedure_id,
        steps=tuple(step_from_wire(s) for s in body.steps),
    )
    result = await handler(
        command,
        principal_id=principal_id,
        correlation_id=cid,
        surface_id=surface_id,
    )
    return result_to_wire(result)

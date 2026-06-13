"""HTTP setup for the Operation BC.

`register_operation_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, `ConcurrencyError`, and `AssetNotFoundError`
(Equipment-BC) are infra-layer / cross-BC errors registered by their
owning BC. They produce the same JSON shape regardless of which BC
raised them, so Operation does not re-register them.

## Loop-collapse pattern

Operation owns one aggregate (Procedure) plus its per-step logbook.
Five error families share the same response shape and get collapsed
via the Trust / Equipment / Supply-style loop pattern:

  - 400 (validation): InvalidProcedureName, InvalidProcedureKind,
    InvalidProcedureAbortReason, InvalidProcedureTruncateReason,
    InvalidProcedureInterruptedAt, InvalidStepKind
  - 404 (load miss): ProcedureNotFound
  - 409 (defensive guard for AlreadyExists): ProcedureAlreadyExists
  - 409 (transition guards): ProcedureCannotStart,
    ProcedureCannotComplete, ProcedureCannotAbort,
    ProcedureCannotTruncate, ProcedurePlanAssetDecommissioned,
    ProcedureStepsLogbookClosed
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.operation.aggregates.procedure import (
    InvalidProcedureAbortReasonError,
    InvalidProcedureInterruptedAtError,
    InvalidProcedureIterationCapError,
    InvalidProcedureIterationEndReasonError,
    InvalidProcedureKindError,
    InvalidProcedureNameError,
    InvalidProcedureTruncateReasonError,
    InvalidRecipeBindingsError,
    InvalidStepKindError,
    ProcedureAlreadyExistsError,
    ProcedureBoundCapabilityDeprecatedError,
    ProcedureCannotAbortError,
    ProcedureCannotCompleteError,
    ProcedureCannotEndIterationError,
    ProcedureCannotStartError,
    ProcedureCannotStartIterationError,
    ProcedureCannotTruncateError,
    ProcedureCapabilityExecutorMismatchError,
    ProcedureEnclosureCoverageMismatchError,
    ProcedureIterationLimitReachedError,
    ProcedureNotFoundError,
    ProcedurePlanAssetDecommissionedError,
    ProcedureRequiresAvailableSupplyError,
    ProcedureRequiresPermittedEnclosureError,
    ProcedureStepsForbiddenForRecipeDrivenError,
    ProcedureStepsLogbookClosedError,
    ProcedureSupplyCoverageMismatchError,
    RecipeBindingsStaleAgainstCurrentCapabilityError,
    RecipeExpanderVersionMismatchError,
    RecipeExpansionDeterminismError,
    RecipeExpansionOverflowError,
    RecipeExpansionRecordNotFoundError,
    RecipeExpansionReplayMismatchError,
)
from cora.operation.errors import (
    AssetNotPseudoAxisError,
    PartitionRuleNotFoundError,
    PseudoAxisConstituentDispatchError,
    PseudoAxisConstituentNotFoundError,
    PseudoAxisConstituentUnauthorizedError,
    PseudoAxisEvaluationFailedError,
    PseudoAxisSingularityExceededError,
    UnauthorizedError,
)
from cora.operation.features import (
    abort_procedure,
    append_activities,
    complete_procedure,
    conduct_procedure,
    end_iteration,
    get_procedure,
    list_procedure_iterations,
    list_procedures,
    register_procedure,
    register_procedure_from_recipe,
    start_iteration,
    start_procedure,
    truncate_procedure,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error.

    Covers Invalid<X>NameError / Invalid<X>KindError /
    Invalid<X>AbortReasonError. All map to HTTP 400 +
    `{"detail": str(exc)}` body. Adding a new validation-style error
    is one extra entry in the tuple in `register_operation_routes`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for every aggregate's AlreadyExistsError.

    The decider raises these if the target stream already has events.
    In production with UUIDv7 ids this is essentially impossible, but
    the unmapped raise would surface as 500 instead of a clean 409 --
    this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for every transition-guard error.

    Covers ProcedureCannotStart / ProcedureCannotComplete /
    ProcedureCannotAbort / ProcedureCannotTruncate (FSM source-state
    guards), ProcedurePlanAssetDecommissioned (cross-aggregate precondition
    guard at start_procedure), AND ProcedureStepsLogbookClosed (logbook
    write guard for non-Running Procedures). All map to HTTP 409 +
    `{"detail": str(exc)}`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_unprocessable(request: Request, exc: Exception) -> JSONResponse:
    """Shared 422 handler for parse-shape failures past the Pydantic boundary.

    Covers the Recipe-expansion family raised at
    register_procedure_from_recipe time: stale-Capability schema drift,
    operator-supplied bindings shape failures, and the expansion
    overflow cap. The 400 Invalid<X> family is reserved for VO
    constructor failures (name / kind); 422 is reserved for
    downstream parse-shape or schema-cross-check failures that pass
    Pydantic but fail at the cross-aggregate boundary.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


async def _handle_internal_server_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 500 handler for server-side determinism / port-contract bugs.

    Covers RecipeExpansionDeterminismError (expansion port returned
    different results for the same `(steps, bindings)` input,
    indicating a non-pure expander or a non-canonical bindings dict).
    Distinct from operator error: the operator's request is well-formed;
    the server-side bug means re-trying with the same payload will
    likely fail the same way. Mapped to HTTP 500.

    Also covers `PseudoAxisEvaluationFailedError`: the partition-rule
    math kernel produced a non-finite result, a NaN, or an unsupported
    rule variant. Operator command shape was valid; the server-side
    failure is in the evaluator. Per [[project-pseudoaxis-design]] v3
    HTTP status map: 500.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc)},
    )


async def _handle_bad_gateway(request: Request, exc: Exception) -> JSONResponse:
    """Shared 502 handler for downstream substrate-dispatch failures.

    Covers `PseudoAxisConstituentDispatchError`: a constituent
    ControlPort write rejected the resolved setpoint mid-dispatch.
    Operator request was well-formed and the evaluator's math
    succeeded; the failure is in the downstream substrate (network,
    IOC unreachable, write rejected by hardware). Per
    [[project-pseudoaxis-design]] v3 HTTP status map: 502.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": str(exc)},
    )


def register_operation_routes(app: FastAPI) -> None:
    """Attach Operation slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_procedure.router)
    app.include_router(register_procedure_from_recipe.router)
    app.include_router(start_procedure.router)
    app.include_router(complete_procedure.router)
    app.include_router(abort_procedure.router)
    app.include_router(truncate_procedure.router)
    app.include_router(start_iteration.router)
    app.include_router(end_iteration.router)
    app.include_router(append_activities.router)
    app.include_router(get_procedure.router)
    app.include_router(list_procedures.router)
    app.include_router(list_procedure_iterations.router)
    app.include_router(conduct_procedure.router)
    for validation_cls in (
        InvalidProcedureNameError,
        InvalidProcedureKindError,
        InvalidProcedureAbortReasonError,
        InvalidProcedureTruncateReasonError,
        InvalidProcedureIterationEndReasonError,
        InvalidProcedureIterationCapError,
        InvalidProcedureInterruptedAtError,
        InvalidStepKindError,
        # Recipe-driven conduct_procedure path: caller-supplied steps with
        # recipe_id set are rejected up front per the replay-design lock
        # ([[project-run-procedure-replay-design]] Anti-hook 7).
        ProcedureStepsForbiddenForRecipeDrivenError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (ProcedureNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    # NOT registered here: CapabilityNotFoundError (Recipe BC owns; raised
    # from register_procedure's handler but the HTTP mapping lives in
    # recipe/routes.py — FastAPI's app-scoped handler catches regardless
    # of which BC's route raises). Same single-registration rule as
    # decision/routes.py owning ParentDecision*MismatchError for agent
    # BC's regenerate_run_debrief slice.
    for already_exists_cls in (ProcedureAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        ProcedureCannotStartError,
        ProcedureCannotCompleteError,
        ProcedureCannotAbortError,
        ProcedureCannotTruncateError,
        # iteration boundary guards (start/end): not-Running, no/already-open
        # iteration, and non-sequential / mismatched operator-supplied index.
        ProcedureCannotStartIterationError,
        ProcedureCannotEndIterationError,
        # patience cap exhausted: the convergence loop gave up after N
        # consecutive unconverged iterations (operator-actionable: abort
        # or complete the Procedure).
        ProcedureIterationLimitReachedError,
        ProcedurePlanAssetDecommissionedError,
        ProcedureStepsLogbookClosedError,
        # cross-BC guard: Procedure binds to a Capability whose
        # executor_shapes does not include Procedure.
        ProcedureCapabilityExecutorMismatchError,
        # cross-BC Capability-deprecation gate at conduct_procedure
        # for recipe-driven Procedures. Symmetric to start_run's
        # RunBoundPlanDeprecatedError; closes the deprecation-at-
        # execution-time gap surfaced by the 2026-06-04 domain
        # harmony audit.
        ProcedureBoundCapabilityDeprecatedError,
        # cross-BC Supply pre-flight gate (Phase-of-Run only).
        ProcedureRequiresAvailableSupplyError,
        ProcedureSupplyCoverageMismatchError,
        # cross-BC Enclosure pre-flight gate per
        # [[project_enclosure_stage1_design]] L-pre-1.
        ProcedureRequiresPermittedEnclosureError,
        ProcedureEnclosureCoverageMismatchError,
        # PseudoAxis pre-Conductor expansion ([[project-pseudoaxis-design]]
        # v3): the routing layer dispatched a virtual-axis setpoint
        # into the evaluator for an Asset whose Family is not PseudoAxis
        # (routing bug surfaced as 409) OR the PseudoAxis Asset has no
        # partition rule set (operator-recoverable: set the rule via
        # `update_asset_partition_rule` then retry).
        AssetNotPseudoAxisError,
        PartitionRuleNotFoundError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    for unprocessable_cls in (
        # Recipe-expansion family at register_procedure_from_recipe time.
        # All fire AFTER Pydantic body validation: stale-Capability schema
        # drift, operator-bindings shape failure, expansion overflow cap.
        RecipeBindingsStaleAgainstCurrentCapabilityError,
        InvalidRecipeBindingsError,
        RecipeExpansionOverflowError,
        # PseudoAxis pre-Conductor expansion ([[project-pseudoaxis-design]]
        # v3): evaluator-input shape failures the operator can correct.
        # ConstituentNotFound = the partition rule references a constituent
        # Asset the Equipment BC cannot resolve. SingularityExceeded =
        # SolverReference rule's post-solve residual exceeded the declared
        # singularity_threshold (the requested pose is mathematically
        # singular for the configured solver).
        PseudoAxisConstituentNotFoundError,
        PseudoAxisSingularityExceededError,
    ):
        app.add_exception_handler(unprocessable_cls, _handle_unprocessable)
    # Server-side determinism bugs / data corruption: HTTP 500. Distinct
    # from operator-error 422 because re-trying with the same payload
    # will fail the same way. Replay-time bugs land here too per
    # [[project-run-procedure-replay-design]] Rejections (alphabetical):
    #   - RecipeExpansionDeterminismError (at-write determinism bug).
    #   - RecipeExpanderVersionMismatchError (pinned port v differs
    #     from currently-wired; placeholder until a v2 expansion port
    #     lands with its routing layer).
    #   - RecipeExpansionRecordNotFoundError (data corruption guard:
    #     recipe_id set but the pinned RecipeExpansionRecorded event or
    #     the pinned Recipe stream cannot be located).
    #   - RecipeExpansionReplayMismatchError (replay-time hash drift).
    for internal_cls in (
        RecipeExpansionDeterminismError,
        RecipeExpanderVersionMismatchError,
        RecipeExpansionRecordNotFoundError,
        RecipeExpansionReplayMismatchError,
        # PseudoAxis pre-Conductor expansion ([[project-pseudoaxis-design]]
        # v3): the partition-rule math kernel returned a non-finite result,
        # rejected an unsupported AggregatorKind / PartitionKind variant,
        # or refused a LookupTable for which the kernel is not yet wired.
        # The operator command was well-formed; re-trying the same payload
        # will likely fail the same way. 500.
        PseudoAxisEvaluationFailedError,
    ):
        app.add_exception_handler(internal_cls, _handle_internal_server_error)
    # PseudoAxis constituent-dispatch substrate failures land as 502:
    # the upstream evaluator succeeded but a downstream ControlPort write
    # to one of the resolved constituents failed mid-dispatch (substrate
    # rejection, network drop, IOC unreachable). Distinct from 500
    # because the failure is in the substrate, not the server.
    app.add_exception_handler(PseudoAxisConstituentDispatchError, _handle_bad_gateway)
    # PseudoAxis constituent-Surface authorization failures land as 403:
    # the pre-dispatch authz sweep rejected the principal's permission
    # against one of the constituent Assets' Surface. Pre-flight, NOT
    # mid-dispatch; the whole command is rejected at acceptance time.
    app.add_exception_handler(PseudoAxisConstituentUnauthorizedError, _handle_unauthorized)
    # NOT registered here: RecipeVersionNotFoundError (Recipe BC owns;
    # raised from conduct_procedure handler via load_recipe_at_version
    # but HTTP mapping lives in recipe/routes.py per the same cross-BC
    # single-registration rule as CapabilityNotFoundError above).
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)

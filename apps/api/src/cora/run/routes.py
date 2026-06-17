"""HTTP setup for the Run BC.

`register_run_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Run
does not re-register them.

## Loop-collapse pattern

Mirrors Recipe / Equipment / Subject. Generic error handlers per
family, tuple loops to register them. The truncate transition has
its own handler + guard errors (RunCannotTruncateError + two
validation errors: InvalidRunTruncateReasonError +
InvalidRunInterruptedAtError).

  - 400 (validation): InvalidRunNameError, InvalidRunAbortReasonError,
    InvalidRunStopReasonError, InvalidRunTruncateReasonError,
    InvalidRunInterruptedAtError, InvalidRunParametersError,
    InvalidChannelNameError, InvalidObservationValueError,
    InvalidSamplingProcedureError, InvalidRunExternalRefError
  - 404 (load miss): RunNotFoundError
  - 409 (defensive guard for AlreadyExists): RunAlreadyExistsError
  - 409 (Run-start binding-state guards): RunBoundPlanDeprecatedError,
    RunSubjectNotMountableError, RunPlanAssetDecommissionedError,
    RunCapabilitiesNotSatisfiedError
  - 409 (Run-start safety-clearance gate, 11a-c-3):
    RunRequiresActiveClearanceError, RunClearanceCoverageMismatchError
  - 409 (Run-start supply pre-flight gate):
    RunRequiresAvailableSupplyError, RunSupplyCoverageMismatchError
  - 409 (Run transition guards, 6f-2): RunCannotCompleteError,
    RunCannotAbortError
  - 409 (Run transition guards, 6f-3): RunCannotHoldError,
    RunCannotResumeError, RunCannotStopError
  - 409 (Run transition guards, 6f-4): RunCannotTruncateError
  - 409 (observation logbook guard, 6f-5b): RunObservationLogbookClosedError
  - 400 (Run adjust validation guards, 6j): InvalidRunAdjustPatchError,
    InvalidRunAdjustSchemaError, InvalidRunAdjustReasonError
  - 409 (Run adjust transition guard, 6j): RunCannotAdjustError
  - 400 (validation, 12b-5 adds): InvalidPinnedCalibrationsError
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.run.aggregates.run import (
    InvalidChannelNameError,
    InvalidObservationValueError,
    InvalidPinnedCalibrationsError,
    InvalidRunAbortReasonError,
    InvalidRunAdjustPatchError,
    InvalidRunAdjustReasonError,
    InvalidRunAdjustSchemaError,
    InvalidRunExternalRefError,
    InvalidRunInterruptedAtError,
    InvalidRunNameError,
    InvalidRunParametersError,
    InvalidRunStopReasonError,
    InvalidRunTruncateReasonError,
    InvalidSamplingProcedureError,
    RunAlreadyAssignedToCampaignError,
    RunAlreadyExistsError,
    RunBeamAvailabilityUnknownError,
    RunBoundPlanDeprecatedError,
    RunCannotAbortError,
    RunCannotAdjustError,
    RunCannotCompleteError,
    RunCannotHoldError,
    RunCannotJoinCampaignError,
    RunCannotResumeError,
    RunCannotStopError,
    RunCannotTruncateError,
    RunCapabilitiesNotSatisfiedError,
    RunClearanceCoverageMismatchError,
    RunEnclosureCoverageMismatchError,
    RunNotFoundError,
    RunObservationLogbookClosedError,
    RunPlanAssetDecommissionedError,
    RunRequiresActiveClearanceError,
    RunRequiresAvailableSupplyError,
    RunRequiresOpenBeamShuttersError,
    RunRequiresPermittedEnclosureError,
    RunSubjectNotMountableError,
    RunSupplyCoverageMismatchError,
)
from cora.run.errors import UnauthorizedError
from cora.run.features import (
    abort_run,
    adjust_run,
    append_observations,
    complete_run,
    get_run,
    hold_run,
    list_runs,
    resume_run,
    start_run,
    stop_run,
    truncate_run,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error."""
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
    """Shared 404 handler for the aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for RunAlreadyExistsError.

    The decider raises this if the target stream already has events.
    In production with UUIDv7 ids this is essentially impossible, but
    the unmapped raise would surface as 500 instead of a clean 409.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for binding-state and transition guards.

    Covers Run-start binding-state guards (Plan deprecated, Subject
    not mountable, Asset decommissioned, capabilities not satisfied)
    plus Run transition guards (cannot complete / abort / hold /
    resume / stop / truncate).
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_run_routes(app: FastAPI) -> None:
    """Attach Run slice routers and exception handlers to the FastAPI app."""
    app.include_router(start_run.router)
    app.include_router(complete_run.router)
    app.include_router(abort_run.router)
    app.include_router(hold_run.router)
    app.include_router(resume_run.router)
    app.include_router(stop_run.router)
    app.include_router(truncate_run.router)
    app.include_router(adjust_run.router)
    app.include_router(append_observations.router)
    app.include_router(get_run.router)
    app.include_router(list_runs.router)
    for validation_cls in (
        InvalidRunNameError,
        InvalidRunAbortReasonError,
        InvalidRunStopReasonError,
        InvalidRunTruncateReasonError,
        InvalidRunInterruptedAtError,
        InvalidRunParametersError,
        # Reading-entry validation guards (6f-5b).
        InvalidChannelNameError,
        InvalidObservationValueError,
        InvalidSamplingProcedureError,
        # ExternalRef validation guard (11a-c-3).
        InvalidRunExternalRefError,
        # Adjust validation guards (6j).
        InvalidRunAdjustPatchError,
        InvalidRunAdjustReasonError,
        InvalidRunAdjustSchemaError,
        # Pin-set cardinality cap on AsShot citation (12b-5; symmetric
        # to Data BC's InvalidUsedCalibrationsError on register_dataset).
        InvalidPinnedCalibrationsError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (RunNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (RunAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        # Run-start binding-state guards.
        RunBoundPlanDeprecatedError,
        RunSubjectNotMountableError,
        RunPlanAssetDecommissionedError,
        RunCapabilitiesNotSatisfiedError,
        # Run-start safety-clearance gate (11a-c-3).
        RunRequiresActiveClearanceError,
        RunClearanceCoverageMismatchError,
        # Run-start supply pre-flight gate.
        RunRequiresAvailableSupplyError,
        RunSupplyCoverageMismatchError,
        # Run-start enclosure pre-flight gate per
        # [[project_enclosure_stage1_design]] L-pre-1.
        RunRequiresPermittedEnclosureError,
        RunEnclosureCoverageMismatchError,
        # Run-start beam-availability pre-flight gate (BEAM-1):
        # closed shutters / denied permit, and the fail-closed
        # unknown branch when a beam PV could not be read.
        RunRequiresOpenBeamShuttersError,
        RunBeamAvailabilityUnknownError,
        # Run-start campaign-membership gate (6i-c).
        RunCannotJoinCampaignError,
        # Run-side campaign-membership invariant (6i-c).
        RunAlreadyAssignedToCampaignError,
        # Run transition guards (6f-2).
        RunCannotCompleteError,
        RunCannotAbortError,
        # Run transition guards (6f-3).
        RunCannotHoldError,
        RunCannotResumeError,
        RunCannotStopError,
        # Run transition guards (6f-4).
        RunCannotTruncateError,
        # Reading logbook closed (6f-5b): Run is in a terminal status.
        RunObservationLogbookClosedError,
        # Run adjust transition guard (6j).
        RunCannotAdjustError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)

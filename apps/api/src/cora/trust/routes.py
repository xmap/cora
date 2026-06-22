"""HTTP setup for the Trust BC.

`register_trust_routes(app)` includes every slice's router and registers
exception handlers that translate the BC's domain / application errors
to HTTP status codes. Called once at app construction.

Routers attached:
  - define_zone / define_conduit / define_policy (3a-c, command slices)
  - evaluate_policy (3d, first query slice)
  - list_zones / list_conduits / list_policies (8e-8, projection-
    backed list slices closing read-side coverage)

JSONResponse is used (not HTTPException) per FastAPI guidance to avoid
nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce
the same JSON shape regardless of which BC raised them, so Trust does
not re-register them. A `ZoneNotFoundError` (or analogous "missing
target" handler) lands here once the first slice that loads-and-folds
the Zone stream ships; per YAGNI it doesn't exist yet.

## Loop-collapse pattern

Mirrors Run / Recipe / Equipment / Subject. Generic error handlers
per family, tuple loops to register them. Status-code groupings:

  - 400 (validation): InvalidZoneNameError, InvalidConduitNameError,
    InvalidPolicyNameError
  - 403 (authz): UnauthorizedError
  - 409 (defensive guard for AlreadyExists): ZoneAlreadyExistsError,
    ConduitAlreadyExistsError, PolicyAlreadyExistsError
  - 409 (Conduit logbook state guards): ConduitLogbookAlreadyOpenError,
    ConduitLogbookNotOpenError
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.trust.aggregates.conduit import (
    ConduitAlreadyExistsError,
    ConduitLogbookAlreadyOpenError,
    ConduitLogbookNotOpenError,
    InvalidConduitNameError,
)
from cora.trust.aggregates.policy import (
    InvalidPolicyNameError,
    InvalidPolicySurfaceError,
    PolicyAlreadyExistsError,
)
from cora.trust.aggregates.surface import InvalidSurfaceNameError, SurfaceAlreadyExistsError
from cora.trust.aggregates.visit import (
    InvalidVisitPlannedPeriodError,
    InvalidVisitReasonError,
    VisitActorNotCheckedInError,
    VisitAlreadyCheckedInError,
    VisitAlreadyExistsError,
    VisitCannotAbortError,
    VisitCannotArriveError,
    VisitCannotCancelError,
    VisitCannotCheckInError,
    VisitCannotCompleteError,
    VisitCannotHoldError,
    VisitCannotReleaseControlError,
    VisitCannotResumeError,
    VisitCannotStartError,
    VisitCannotTakeControlError,
    VisitCannotVoidError,
    VisitNotFoundError,
    VisitParentMismatchedSurfaceError,
    VisitParentNotFoundError,
)
from cora.trust.aggregates.zone import InvalidZoneNameError, ZoneAlreadyExistsError
from cora.trust.errors import UnauthorizedError
from cora.trust.features import (
    abort_visit,
    cancel_visit,
    check_in_visit,
    check_out_visit,
    complete_visit,
    define_conduit,
    define_policy,
    define_surface,
    define_zone,
    evaluate_policy,
    get_surface,
    hold_visit,
    list_conduits,
    list_permissions,
    list_policies,
    list_zones,
    record_visit_arrival,
    register_visit,
    release_control_of_surface,
    resume_visit,
    start_visit,
    take_control_of_surface,
    void_visit,
)


async def _handle_invalid_name(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every aggregate's `Invalid<Aggregate>NameError`.

    All three Trust aggregate name VOs raise the same shape of error
    (whitespace-only / empty / too-long), and all three map to the
    same HTTP 400 + `{"detail": str}` body. One handler registered
    against three exception classes; adding a fourth aggregate just
    appends to the loop in `register_trust_routes`.
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


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for `<Aggregate>AlreadyExistsError`.

    The decider raises this if the target stream already has events.
    With UUIDv7 ids this is essentially impossible in production, but
    the unmapped raise would surface as 500 instead of a clean 409.
    Mirrors the Run BC's pattern.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_logbook_state(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for Conduit logbook state guards.

    `ConduitLogbookAlreadyOpenError` (open attempted while the kind
    already has an open logbook) and `ConduitLogbookNotOpenError`
    (close attempted on an id that's not currently open). Both
    encode the at-most-one-open-per-kind invariant.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for `<Aggregate>NotFoundError` (Visit + future)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_invalid_400(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for domain `Invalid<X>Error` (non-name variants)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_visit_conflict_409(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for Visit transition / partOf / control guards."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_trust_routes(app: FastAPI) -> None:
    """Attach Trust slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_zone.router)
    app.include_router(define_conduit.router)
    app.include_router(define_policy.router)
    app.include_router(define_surface.router)
    app.include_router(evaluate_policy.router)
    app.include_router(get_surface.router)
    app.include_router(list_zones.router)
    app.include_router(list_conduits.router)
    app.include_router(list_policies.router)
    app.include_router(list_permissions.router)
    # Visit lifecycle slices.
    app.include_router(register_visit.router)
    app.include_router(record_visit_arrival.router)
    app.include_router(start_visit.router)
    app.include_router(hold_visit.router)
    app.include_router(resume_visit.router)
    app.include_router(complete_visit.router)
    app.include_router(cancel_visit.router)
    app.include_router(abort_visit.router)
    app.include_router(void_visit.router)
    # Visit presence slices.
    app.include_router(check_in_visit.router)
    app.include_router(check_out_visit.router)
    # Visit Surface-control slices.
    app.include_router(take_control_of_surface.router)
    app.include_router(release_control_of_surface.router)
    for invalid_name_cls in (
        InvalidZoneNameError,
        InvalidConduitNameError,
        InvalidPolicyNameError,
        InvalidSurfaceNameError,
    ):
        app.add_exception_handler(invalid_name_cls, _handle_invalid_name)
    for already_exists_cls in (
        ZoneAlreadyExistsError,
        ConduitAlreadyExistsError,
        PolicyAlreadyExistsError,
        SurfaceAlreadyExistsError,
        VisitAlreadyExistsError,
        # VisitAlreadyCheckedInError reuses 409 (semantically an exists-conflict).
        VisitAlreadyCheckedInError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for logbook_state_cls in (
        ConduitLogbookAlreadyOpenError,
        ConduitLogbookNotOpenError,
    ):
        app.add_exception_handler(logbook_state_cls, _handle_logbook_state)
    # Visit 404 + 400 + 409 (lifecycle + control) handlers.
    # VisitActorNotCheckedInError reuses 404 (semantically a not-found condition).
    # VisitParentNotFoundError reuses 404 (missing parent stream).
    for not_found_cls in (
        VisitNotFoundError,
        VisitActorNotCheckedInError,
        VisitParentNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for invalid_400_cls in (
        InvalidPolicySurfaceError,
        InvalidVisitPlannedPeriodError,
        InvalidVisitReasonError,
    ):
        app.add_exception_handler(invalid_400_cls, _handle_invalid_400)
    for cannot_409_cls in (
        VisitCannotAbortError,
        VisitCannotArriveError,
        VisitCannotCancelError,
        VisitCannotCheckInError,
        VisitCannotCompleteError,
        VisitCannotHoldError,
        VisitCannotReleaseControlError,
        VisitCannotResumeError,
        VisitCannotStartError,
        VisitCannotTakeControlError,
        VisitCannotVoidError,
        VisitParentMismatchedSurfaceError,
    ):
        app.add_exception_handler(cannot_409_cls, _handle_visit_conflict_409)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)

"""HTTP setup for the Enclosure BC.

`register_enclosure_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots). They produce the
same JSON shape regardless of which BC raised them, so Enclosure
does not re-register them.

## Loop-collapse pattern

Enclosure owns one aggregate (Enclosure). Domain errors share
response shape and get collapsed via the Supply / Facility-style
loop pattern:

  - 400 (validation): InvalidEnclosureName, InvalidEnclosureReason,
    InvalidMonitorRef, MonitorTriggerNotPermitted
  - 404 (not-found): EnclosureNotFound, EnclosureFacilityNotFound
  - 409 (state-transition guards): EnclosureCannotDecommission,
    EnclosureCannotObserveWhileDecommissioned
  - 409 (defensive guard for AlreadyExists): EnclosureAlreadyExists
  - 403 (application-layer auth): UnauthorizedError

`MonitorTriggerNotPermittedError` rides the 400 family rather than
the 409 cannot-transition family: it rejects command intent (an
inbound observation carrying a non-Monitor trigger), not aggregate
state. The mapping is defense-in-depth: the
`observe_enclosure_status` slice is invoked in-process by the
EnclosureObserver adapter loop and exposes no public HTTP surface,
so the handler is unreachable through routes today. The entry
future-proofs an eventual operator-override REST surface and keeps
the error well-formed if any other code path surfaces it through
FastAPI.

Adding a new aggregate (or a new transition error) becomes one tuple
entry per family.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.enclosure.aggregates._value_types import (
    InvalidEnclosureReasonError,
    InvalidMonitorRefError,
)
from cora.enclosure.aggregates.enclosure import (
    EnclosureAlreadyExistsError,
    EnclosureCannotDecommissionError,
    EnclosureCannotObserveWhileDecommissionedError,
    EnclosureFacilityNotFoundError,
    EnclosureNotFoundError,
    InvalidEnclosureNameError,
    MonitorTriggerNotPermittedError,
)
from cora.enclosure.errors import UnauthorizedError
from cora.enclosure.features import (
    decommission_enclosure,
    observe_enclosure_status,
    register_enclosure,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error.

    Covers Invalid<X>NameError VOs and command-intent rejections
    such as `MonitorTriggerNotPermittedError`. All map to the same
    HTTP 400 + `{"detail": str(exc)}` body. Adding a new
    validation-style error is one extra entry in the tuple in
    `register_enclosure_routes`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


async def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards (Cannot<Verb>Error family)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler for every aggregate's AlreadyExistsError.

    The handler raises this when the target stream already has events
    (translated from `ConcurrencyError` on `append(expected_version=0)`).
    In production with UUIDv7 ids this is essentially impossible, but
    the unmapped raise would surface as 500 instead of a clean 409;
    this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_unauthorized(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    reason = exc.reason if isinstance(exc, UnauthorizedError) else str(exc)
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": reason},
    )


def register_enclosure_routes(app: FastAPI) -> None:
    """Attach Enclosure slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_enclosure.router)
    app.include_router(decommission_enclosure.router)
    # Stub router inclusion for the in-process-only observe slice. The
    # router carries no routes by design; this include satisfies the
    # routes-completeness architecture fitness without exposing a
    # public HTTP surface.
    app.include_router(observe_enclosure_status.router)
    for validation_cls in (
        InvalidEnclosureNameError,
        InvalidEnclosureReasonError,
        InvalidMonitorRefError,
        MonitorTriggerNotPermittedError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (EnclosureNotFoundError, EnclosureFacilityNotFoundError):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (EnclosureAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        EnclosureCannotDecommissionError,
        EnclosureCannotObserveWhileDecommissionedError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)

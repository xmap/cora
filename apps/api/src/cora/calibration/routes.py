"""HTTP setup for the Calibration BC.

`register_calibration_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

## Error families

  - 400 (validation): InvalidCalibrationDescriptionError,
    InvalidCalibrationQuantityError, InvalidOperatingPointError,
    InvalidCalibrationValueError, InvalidCalibrationSourceError,
    SupersedesRevisionNotFoundError
  - 403 (authz): UnauthorizedError
  - 404 (load miss): CalibrationNotFoundError
  - 409 (defensive guard for AlreadyExists): CalibrationAlreadyExistsError,
    CalibrationIdentityAlreadyExistsError (raised when the projection's
    jsonb-UNIQUE catches a duplicate-identity insert; the slice itself
    does NOT pre-check the projection per the design memo's deferred
    lookup-port watch item)
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.calibration.aggregates.calibration import (
    CalibrationAlreadyExistsError,
    CalibrationCannotPublishRevisionError,
    CalibrationIdentityAlreadyExistsError,
    CalibrationNotFoundError,
    CalibrationNotLookupValuedError,
    CalibrationRevisionNotFoundError,
    InvalidCalibrationDescriptionError,
    InvalidCalibrationQuantityError,
    InvalidCalibrationSourceError,
    InvalidCalibrationValueError,
    InvalidOperatingPointError,
    OutboundPermitNotActiveError,
    SupersedesRevisionNotFoundError,
)
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features import (
    append_calibration_revision,
    define_calibration,
    get_calibration,
    list_calibrations,
    publish_revision,
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
    """Shared 404 handler for every aggregate's NotFoundError."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_conflict(request: Request, exc: Exception) -> JSONResponse:
    """409 handler for publish-time FSM-rejection errors.

    Covers OutboundPermitNotActiveError and
    CalibrationCannotPublishRevisionError: the publish slice cannot
    proceed because the permit is not Active or the revision lacks
    a content_hash. Distinct from 422 because the request shape is
    valid; the state of the world does not allow the action.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    """Defensive 409 handler.

    Covers both the stream-genesis collision (CalibrationAlreadyExistsError,
    essentially impossible in production with UUIDv7 ids) and the
    identity-tuple uniqueness collision (CalibrationIdentityAlreadyExistsError,
    raised by the projection's jsonb-UNIQUE). The routes layer maps
    both to 409 since both surface to the operator as "this
    calibration already exists".
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_calibration_routes(app: FastAPI) -> None:
    """Attach Calibration slice routers and exception handlers to the FastAPI app."""
    app.include_router(define_calibration.router)
    app.include_router(append_calibration_revision.router)
    app.include_router(publish_revision.router)
    app.include_router(get_calibration.router)
    app.include_router(list_calibrations.router)
    for validation_cls in (
        InvalidCalibrationDescriptionError,
        InvalidCalibrationQuantityError,
        InvalidOperatingPointError,
        InvalidCalibrationValueError,
        InvalidCalibrationSourceError,
        SupersedesRevisionNotFoundError,
        # A LookupTable partition rule pinned a scalar-valued calibration;
        # raised at conduct time from load_pinned_lookup. App-scoped, so it
        # surfaces from the Operation conduct path too (400, operator
        # re-points the rule).
        CalibrationNotLookupValuedError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        CalibrationNotFoundError,
        CalibrationRevisionNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        CalibrationAlreadyExistsError,
        CalibrationIdentityAlreadyExistsError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for conflict_cls in (
        CalibrationCannotPublishRevisionError,
        OutboundPermitNotActiveError,
    ):
        app.add_exception_handler(conflict_cls, _handle_conflict)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)

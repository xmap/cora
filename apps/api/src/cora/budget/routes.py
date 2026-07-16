"""HTTP setup for the budget BC.

`register_budget_routes(app)` includes every slice's router and
registers exception handlers that translate the BC's domain /
application errors to HTTP status codes. Called once at app
construction.

JSONResponse is used (not HTTPException) per FastAPI guidance to
avoid nested-exception pitfalls.

`IdempotencyConflictError`, `IdempotencyClaimLostError`,
`CachedHandlerError`, and `ConcurrencyError` are infra-layer errors
registered by Access (the first BC that boots); budget does not
re-register them.

## Loop-collapse pattern

Budget owns one aggregate. Four error families share response shapes
and get collapsed via the Campaign / Trust / Equipment / Supply loop
pattern:

  - 400 (validation): InvalidAllocationCeiling,
    InvalidAllocationNote, InvalidAllocationReason
  - 404 (load miss): AllocationNotFound
  - 409 (defensive guard for AlreadyExists): AllocationAlreadyExists
  - 409 (transition guards): AllocationCannotActivate,
    AllocationCannotAmend, AllocationCannotSeal, AllocationCannotVoid
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.budget.aggregates.allocation import (
    AllocationAlreadyActiveError,
    AllocationAlreadyExistsError,
    AllocationCannotActivateError,
    AllocationCannotAmendCeilingError,
    AllocationCannotSealError,
    AllocationCannotVoidError,
    AllocationNotFoundError,
    InvalidAllocationCeilingError,
    InvalidAllocationNoteError,
    InvalidAllocationReasonError,
)
from cora.budget.errors import UnauthorizedError
from cora.budget.features import (
    activate_allocation,
    amend_allocation_ceiling,
    grant_allocation,
    seal_allocation,
    void_allocation,
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
    """Defensive 409 handler for the aggregate's AlreadyExistsError.

    The decider raises it when the target stream already has events.
    In production with server-minted UUIDv7 ids this is essentially
    impossible (caller-supplied ids make it reachable), but the
    unmapped raise would surface as 500 instead of a clean 409.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers the `AllocationCannot<Verb>Error` family: Activate, Amend,
    Seal, Void. Same pattern as Campaign / Supply / Safety
    `_handle_cannot_transition`.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_budget_routes(app: FastAPI) -> None:
    """Attach budget slice routers and exception handlers to the FastAPI app."""
    app.include_router(grant_allocation.router)
    app.include_router(activate_allocation.router)
    app.include_router(amend_allocation_ceiling.router)
    app.include_router(seal_allocation.router)
    app.include_router(void_allocation.router)
    for validation_cls in (
        InvalidAllocationCeilingError,
        InvalidAllocationNoteError,
        InvalidAllocationReasonError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (AllocationNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (
        AllocationAlreadyExistsError,
        AllocationAlreadyActiveError,
    ):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (
        AllocationCannotActivateError,
        AllocationCannotAmendCeilingError,
        AllocationCannotSealError,
        AllocationCannotVoidError,
    ):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)

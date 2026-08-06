"""HTTP setup for the Access BC.

`register_access_routes(app)` includes every slice's router and registers
exception handlers that translate the BC's domain / application / infra
errors to HTTP status codes. Called once at app construction (not in
lifespan) so routes are registered before the first request arrives.

JSONResponse is used (not HTTPException) per FastAPI guidance to avoid
nested-exception pitfalls.

## Loop-collapse pattern (cross-BC normalization)

Each error family that maps to one HTTP status code with the same
`{"detail": str(exc)}` body shares one generic handler, registered
against a tuple of error classes via a loop. Adding a new error in
a family is one tuple entry — no new handler function. Mirrors the
shape Equipment + Subject use; Access (the oldest BC) was normalized
so all 4 BCs follow the same pattern.

## Cross-BC infra errors registered here

`ConcurrencyError`, `IdempotencyConflictError`, `IdempotencyClaimLostError`,
and `CachedHandlerError` are infrastructure-layer errors that any BC can
raise. Access (the first BC that boots) registers them globally — Subject /
Trust / Equipment / Recipe / Run / Data / Decision do NOT re-register them.
The JSON shape is the same regardless of which BC issued the error.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.access.aggregates.actor import (
    ActorAlreadyExistsError,
    ActorCannotDeactivateError,
    ActorCannotReactivateError,
    ActorNotFoundError,
    InvalidActorKindError,
    InvalidActorNameError,
)
from cora.access.errors import ActorSelfReactivationRefusedError, UnauthorizedError
from cora.access.features import (
    deactivate_actor,
    forget_actor,
    get_actor,
    list_actors,
    reactivate_actor,
    register_actor,
)
from cora.infrastructure.idempotency import classify_error_status
from cora.infrastructure.ports import (
    CachedHandlerError,
    ConcurrencyError,
    IdempotencyClaimLostError,
    IdempotencyConflictError,
)
from cora.infrastructure.projection import InvalidCursorError


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    """Shared 400 handler for every domain validation error (Invalid<X>...)."""
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

    The decider raises these if the target stream already has
    events. In production with UUIDv7 ids this is essentially
    impossible, but the unmapped raise would surface as 500 instead
    of a clean 409 — this handler closes that gap.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_cannot_transition(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for state-transition guards.

    Covers Subject's `<Bc>Cannot<Verb>Error` family (the locked
    naming convention) and Access's legacy `ActorCannotDeactivateError`
    outlier. Both block a state transition; both return the same
    JSON shape. (Outlier rename to `ActorCannotDeactivateError` is
    deferred until Access grows a 2nd state-transition guard.)
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_concurrency_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Optimistic-concurrency loser. The caller can retry with a fresh load."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_idempotency_conflict(request: Request, exc: Exception) -> JSONResponse:
    """Same Idempotency-Key reused with a different command body — client bug."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


async def _handle_invalid_cursor(request: Request, exc: Exception) -> JSONResponse:
    """Malformed pagination cursor — client passed a corrupt /
    truncated / hand-crafted cursor instead of one from a previous
    response's `next_cursor` field."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


async def _handle_idempotency_claim_lost(request: Request, exc: Exception) -> JSONResponse:
    """Race lost on a concurrent idempotency-key claim. Standard HTTP
    semantics: 409 Conflict + `Retry-After: 1` header tells the client
    (and any standards-conforming SDK) to wait one second and retry.
    The next claim either finds the original request completed (cache
    hit -> same response) or takes over a stale lock (worker crashed)."""
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
        headers={"Retry-After": "1"},
    )


async def _handle_cached_handler_error(request: Request, exc: Exception) -> JSONResponse:
    """A previous handler invocation raised a cacheable 4xx error;
    replay the same status + body. The cached `error_type` (the
    fully-qualified class name) is fed back through the convention-
    based classifier to recover the HTTP status. Falls back to 500
    only if classification fails — that shouldn't happen because only
    4xx-classified errors get cached, but the fallback closes the loop."""
    _ = request
    cached: CachedHandlerError = exc  # type: ignore[assignment]
    short_name = cached.error_type.rsplit(".", 1)[-1]
    # Synthesize a stub exception whose class NAME matches the cached
    # error so the classifier picks the right status. The stub class is
    # defined locally per call (cheap; only fires on cache hit on error
    # path which is uncommon).
    stub = type(short_name, (Exception,), {})()
    http_status = classify_error_status(stub) or 500
    return JSONResponse(
        status_code=http_status,
        content={"detail": cached.error_msg},
    )


def register_access_routes(app: FastAPI) -> None:
    """Attach Access slice routers and exception handlers to the FastAPI app."""
    app.include_router(register_actor.router)
    app.include_router(deactivate_actor.router)
    app.include_router(reactivate_actor.router)
    app.include_router(forget_actor.router)
    app.include_router(get_actor.router)
    app.include_router(list_actors.router)
    for validation_cls in (InvalidActorNameError, InvalidActorKindError):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (ActorNotFoundError,):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (ActorAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    for cannot_transition_cls in (ActorCannotDeactivateError, ActorCannotReactivateError):
        app.add_exception_handler(cannot_transition_cls, _handle_cannot_transition)
    # 403 not 409: self-reactivation is an authority refusal, not a state
    # conflict. The actor genuinely IS deactivated; what is refused is who
    # asked to undo it.
    app.add_exception_handler(ActorSelfReactivationRefusedError, _handle_unauthorized)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
    # Infrastructure errors (cross-BC; Access registers them globally — see module docstring).
    app.add_exception_handler(ConcurrencyError, _handle_concurrency_conflict)
    app.add_exception_handler(IdempotencyConflictError, _handle_idempotency_conflict)
    app.add_exception_handler(IdempotencyClaimLostError, _handle_idempotency_claim_lost)
    app.add_exception_handler(CachedHandlerError, _handle_cached_handler_error)
    app.add_exception_handler(InvalidCursorError, _handle_invalid_cursor)

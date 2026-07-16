"""HTTP setup for the Decision BC.

`register_decision_routes(app)` includes every slice's router and
registers exception handlers translating domain / application
errors to HTTP status codes.

  - 400 (validation): Invalid<X>...Error family + OverrideKindRequiresParentError
                      + InvalidActorKindForDecisionError
  - 404: DecisionNotFoundError, DeciderActorNotFoundError, DecisionParentNotFoundError
  - 409 (defensive AlreadyExists): DecisionAlreadyExistsError
  - 409 (logbook FSM): DecisionLogbookAlreadyOpenError, DecisionLogbookNotOpenError

## Cross-BC infra errors NOT registered here

`ConcurrencyError`, `IdempotencyConflictError`,
`IdempotencyClaimLostError`, `CachedHandlerError`, and
`InvalidCursorError` are infrastructure-layer errors that any BC
can raise. They're registered globally in `cora/access/routes.py`
(the first BC that boots); other BCs do NOT re-register them. The
JSON shape is the same regardless of which BC issued the error.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from cora.decision.aggregates.decision import (
    DeciderActorNotFoundError,
    DecisionAlreadyExistsError,
    DecisionLogbookAlreadyOpenError,
    DecisionLogbookNotOpenError,
    DecisionNotFoundError,
    DecisionParentAgentMismatchError,
    DecisionParentNotFoundError,
    DecisionParentRunMismatchError,
    InvalidDecisionAlternativesError,
    InvalidDecisionChoiceError,
    InvalidDecisionConfidenceError,
    InvalidDecisionContextError,
    InvalidDecisionInputsError,
    InvalidDecisionRatingCommentError,
    InvalidDecisionReasoningError,
    InvalidDecisionRuleError,
    InvalidReasoningSignatureError,
)
from cora.decision.errors import (
    InferenceAgentMismatchError,
    InvalidActorKindForDecisionError,
    OverrideKindRequiresParentError,
    UnauthorizedError,
)
from cora.decision.features import (
    append_inferences,
    get_decision,
    list_decisions,
    rate_decision,
    register_decision,
)


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
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
    _ = request
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def _handle_already_exists(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def _handle_logbook_state(request: Request, exc: Exception) -> JSONResponse:
    """Shared 409 handler for the Decision logbook FSM transition guards.

    Was previously named `_handle_cross_agg_conflict` and covered the
    cross-aggregate Missing*Error family too. Per the locked error
    taxonomy `<X>NotFoundError` is the canonical name (and HTTP 404
    the canonical mapping) for "the referenced thing doesn't exist";
    the renamed `DeciderActorNotFoundError` / `DecisionParentNotFoundError`
    now route through `_handle_not_found`. The only remaining 409-mapped
    family is the logbook state-transition guards, hence the rename.
    Same JSON shape as before.
    """
    _ = request
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


def register_decision_routes(app: FastAPI) -> None:
    """Attach Decision slice routers and exception handlers."""
    app.include_router(register_decision.router)
    app.include_router(get_decision.router)
    app.include_router(append_inferences.router)
    app.include_router(list_decisions.router)
    app.include_router(rate_decision.router)
    for validation_cls in (
        InvalidDecisionChoiceError,
        InvalidDecisionContextError,
        InvalidDecisionReasoningError,
        InvalidDecisionRuleError,
        InvalidDecisionConfidenceError,
        InvalidDecisionAlternativesError,
        InvalidDecisionInputsError,
        InvalidDecisionRatingCommentError,
        InvalidActorKindForDecisionError,
        InvalidReasoningSignatureError,
        OverrideKindRequiresParentError,
        # Parent-chain validators raised by Agent BC's `regenerate_run_debrief`
        # slice. Decision BC owns these errors (defined in
        # aggregates/decision/state.py) so the HTTP mapping lives here;
        # FastAPI's app-scoped handler catches regardless of which BC's
        # route raises them. Agent BC's routes.py does NOT re-register.
        DecisionParentAgentMismatchError,
        DecisionParentRunMismatchError,
    ):
        app.add_exception_handler(validation_cls, _handle_validation_error)
    for not_found_cls in (
        DecisionNotFoundError,
        # Cross-aggregate references; canonical 404 mapping per the
        # locked `<X>NotFoundError` → 404 taxonomy.
        DeciderActorNotFoundError,
        DecisionParentNotFoundError,
    ):
        app.add_exception_handler(not_found_cls, _handle_not_found)
    for already_exists_cls in (DecisionAlreadyExistsError,):
        app.add_exception_handler(already_exists_cls, _handle_already_exists)
    # Logbook-state transition guards (at-most-one-open + close-only-when-open
    # invariants from the Decision logbook aggregate); 409 Conflict.
    for logbook_state_cls in (
        DecisionLogbookAlreadyOpenError,
        DecisionLogbookNotOpenError,
    ):
        app.add_exception_handler(logbook_state_cls, _handle_logbook_state)
    app.add_exception_handler(UnauthorizedError, _handle_unauthorized)
    app.add_exception_handler(InferenceAgentMismatchError, _handle_unauthorized)

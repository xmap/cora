"""Application handler for the `evaluate_policy` query slice.

Cross-BC query-handler shape — same as `get_actor`:

    1. authorize(principal_id, query_name, conduit) -> Allow | Deny
       (caller authz; no-op under AllowAllAuthorize until TrustAuthorize is wired)
    2. load_policy(...)             -> Policy | None  (fold-on-read)
    3. if None -> return None        (route maps to 404)
       else    -> evaluate(...)      (pure PDP from aggregate)

Returns `AuthzResult | None`:
    - `None`  -> the Policy doesn't exist; route layer maps to 404
    - `Allow()`           -> the policy permits the subject tuple
    - `Deny(reason=...)`  -> the policy denies it (with diagnostic reason)

Both Allow and Deny are NORMAL responses (200) — the deny is a
correct, definitive answer, not an error. Only "policy doesn't
exist" is an error case.

Returns the domain `AuthzResult`, not a DTO. The route maps to
`EvaluatePolicyResponse` and the MCP tool maps to its own structured
output. Handlers stay in domain types.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import AuthzResult, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.policy import evaluate, load_policy
from cora.trust.errors import UnauthorizedError
from cora.trust.features.evaluate_policy.query import EvaluatePolicy

_QUERY_NAME = "EvaluatePolicy"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every evaluate_policy handler implements."""

    async def __call__(
        self,
        query: EvaluatePolicy,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult | None: ...


def bind(deps: Kernel) -> Handler:
    """Build an evaluate_policy handler closed over the shared deps."""

    async def handler(
        query: EvaluatePolicy,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> AuthzResult | None:
        _log.info(
            "evaluate_policy.start",
            query_name=_QUERY_NAME,
            policy_id=str(query.policy_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "evaluate_policy.denied",
                query_name=_QUERY_NAME,
                policy_id=str(query.policy_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        policy = await load_policy(deps.event_store, query.policy_id)
        if policy is None:
            _log.info(
                "evaluate_policy.success",
                query_name=_QUERY_NAME,
                policy_id=str(query.policy_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        result = evaluate(
            policy,
            principal_id=query.evaluated_principal_id,
            command_name=query.evaluated_command_name,
            conduit_id=query.evaluated_conduit_id,
            surface_id=query.evaluated_surface_id,
        )

        _log.info(
            "evaluate_policy.success",
            query_name=_QUERY_NAME,
            policy_id=str(query.policy_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            decision=type(result).__name__,
        )
        return result

    return handler

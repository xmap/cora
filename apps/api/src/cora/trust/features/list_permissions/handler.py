"""Application handler for the `list_permissions` query slice.

Loads the Policy, checks principal eligibility + conduit match, and
returns the sorted permitted_commands (or empty list when the
principal isn't eligible). `incomplete=False` always at v1.

Returns `PermissionListing | None` — None when the Policy doesn't
exist (route maps to 404).

Per the design lock anti-hook: callers MUST NOT cache this
result as ground truth for authorization decisions. Only the PEP
(`Kernel.authorize`) authorizes; this is for UX / debugging only.

## On-behalf authz gate (gate-review F2)

Two authz checks run:

  1. `ListPermissions` — the caller's right to invoke the slice at
     all (always required).
  2. `ListPermissionsOfOthers` — the caller's right to enumerate a
     principal OTHER than themselves. Only invoked when
     `evaluated_principal_id != principal_id`.

The bootstrap policy permits `ListPermissions` but NOT
`ListPermissionsOfOthers`, so on-behalf queries fail-closed by
default. Operators who want on-behalf grant the second permission
explicitly via a real admin Policy. AWS SimulatePrincipalPolicy
precedent.

The original memo §6 ("both allowed at v1, no extra permission")
was overruled in gate-review F2: the rationale (PolicyDefined
events already readable) is weak load-bearing on a side-channel
that won't survive the future Budget BC or ABAC.
"""

from typing import Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Allow, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust._authorization_decision import (
    AuthorizationRequest,
    PolicyOnlyContext,
    decide_authorization,
)
from cora.trust.aggregates.policy import load_policy
from cora.trust.errors import UnauthorizedError
from cora.trust.features.list_permissions.query import ListPermissions, PermissionListing

_QUERY_NAME = "ListPermissions"
_ON_BEHALF_QUERY_NAME = "ListPermissionsOfOthers"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every list_permissions handler implements."""

    async def __call__(
        self,
        query: ListPermissions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PermissionListing | None: ...


def bind(deps: Kernel) -> Handler:
    """Build a list_permissions handler closed over the shared deps."""

    async def handler(
        query: ListPermissions,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PermissionListing | None:
        _log.info(
            "list_permissions.start",
            query_name=_QUERY_NAME,
            policy_id=str(query.policy_id),
            evaluated_principal_id=str(query.evaluated_principal_id),
            on_behalf=query.evaluated_principal_id != principal_id,
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
                "list_permissions.denied",
                query_name=_QUERY_NAME,
                policy_id=str(query.policy_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # On-behalf gate (gate-review F2): if the caller is asking about
        # a different principal, require the dedicated permission. The
        # bootstrap policy permits ListPermissions but NOT
        # ListPermissionsOfOthers; operators grant the second one
        # explicitly via a real admin Policy when they want on-behalf.
        if query.evaluated_principal_id != principal_id:
            on_behalf_decision = await deps.authz.authorize(
                principal_id=principal_id,
                command_name=_ON_BEHALF_QUERY_NAME,
                conduit_id=NIL_SENTINEL_ID,
                surface_id=surface_id,
            )
            if isinstance(on_behalf_decision, Deny):
                _log.info(
                    "list_permissions.on_behalf_denied",
                    query_name=_ON_BEHALF_QUERY_NAME,
                    policy_id=str(query.policy_id),
                    principal_id=str(principal_id),
                    evaluated_principal_id=str(query.evaluated_principal_id),
                    correlation_id=str(correlation_id),
                    reason=on_behalf_decision.reason,
                )
                raise UnauthorizedError(on_behalf_decision.reason)

        policy = await load_policy(deps.event_store, query.policy_id)
        if policy is None:
            _log.info(
                "list_permissions.success",
                query_name=_QUERY_NAME,
                policy_id=str(query.policy_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        # Ask the shared decision once per candidate command rather than
        # re-deriving the predicate here. The inline version checked
        # principal and conduit but not surface, so it listed commands as
        # permitted for arrivals the gate refuses; anything this slice
        # reimplements is something it can get wrong on its own.
        #
        # The surface comes from the Policy, not from the caller: a
        # Policy matches its surface by strict equality, so it is the
        # only surface on which the answer is anything but empty. The
        # listing reports it so the set cannot be read as universal.
        permitted_commands = sorted(
            command_name
            for command_name in policy.permitted_commands
            if isinstance(
                decide_authorization(
                    AuthorizationRequest(
                        principal_id=query.evaluated_principal_id,
                        command_name=command_name,
                        conduit_id=query.evaluated_conduit_id,
                        surface_id=policy.surface_id,
                    ),
                    PolicyOnlyContext(policy=policy),
                ),
                Allow,
            )
        )

        result = PermissionListing(
            policy_id=query.policy_id,
            evaluated_principal_id=query.evaluated_principal_id,
            evaluated_conduit_id=query.evaluated_conduit_id,
            surface_id=policy.surface_id,
            permitted_commands=permitted_commands,
            incomplete=False,
        )

        _log.info(
            "list_permissions.success",
            query_name=_QUERY_NAME,
            policy_id=str(query.policy_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            surface_id=str(policy.surface_id),
            permitted_command_count=len(permitted_commands),
        )
        return result

    return handler

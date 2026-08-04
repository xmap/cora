"""The one place an authorization decision is reached.

Three callers ask whether a request is permitted, and until this module
existed all three answered by calling `evaluate(policy, ...)` themselves:
the production gate (`TrustAuthorize`), and the two query slices that
answer questions about a named policy (`evaluate_policy`,
`list_permissions`). While the gate consults nothing but the Policy the
three answers are identical, so the duplication is invisible. It stops
being invisible the moment the gate consults anything else: the gate
would refuse a request on a window, a lifecycle, or an operation class
while the query slices, still evaluating the Policy alone, report the
same request as permitted. Nothing in the type system would notice.

This module is the seam that makes that divergence impossible rather
than merely discouraged. A conjunct is added HERE, once, and every
caller's answer moves together or is explicitly, visibly excluded.

## Why the context is resolved, never passed

The split between `AuthorizationRequest` and `DecisionContext` is the
load-bearing rule, not a grouping convenience:

    AuthorizationRequest   what an enforcement point legitimately knows
                           and therefore supplies: subject, action,
                           resource

    DecisionContext        what the decision point resolves for itself:
                           the policy, and in time the standing, the
                           beamtime, the clock, the budgets

Letting a caller supply anything in the second group inverts the
relationship between enforcement and decision. The concrete failure is
already closed elsewhere in this codebase and must not be reopened here:
a caller who can name the policy it is judged by can name one that
permits it. That is why `TrustAuthorize` binds its policy at
construction and why nothing in `AuthorizationRequest` names a policy.

## Why two context arms that look identical today

`ResolvedContext` and `PolicyOnlyContext` carry the same single field
and will read as duplication inviting a merge. The duplication IS the
enforcement, in the same way the per-window authority types elsewhere in
this bounded context delete a forbidden-field error class by making the
field unrepresentable. Merging them into one type with a nullable
"resolved" flag returns the decision to a runtime check that a future
conjunct can silently skip.

The arms exist so that adding a conjunct is a question the author cannot
avoid answering. When the window conjunct lands, the `ResolvedContext`
arm gains it and the `PolicyOnlyContext` arm must state what it does
instead, because a hypothetical about another principal at another time
has no window to resolve without either leaking that principal's state
or accepting the caller's assertion of it. Both of those are worse than
returning a partial answer that says it is partial.

## Partiality is a return value, not a convention

Every result carries `evaluated`, the set of conjuncts actually
consulted. A query slice cannot forget to mark its answer partial,
because the same function that answered also reported what it skipped.
That is what makes "necessary but not sufficient" checkable at the call
site, in a log, and in a test, rather than a caveat in a docstring
somebody has to have read.
"""

from dataclasses import dataclass
from typing import assert_never
from uuid import UUID

from cora.infrastructure.ports import AuthzResult
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.policy import Policy, evaluate


@dataclass(frozen=True)
class AuthorizationRequest:
    """The subject, action, and resource an enforcement point supplies.

    Everything here is caller-supplied by design. Nothing the decision
    point must resolve for itself belongs on this type; see the module
    docstring for why that boundary is load-bearing.
    """

    principal_id: UUID
    command_name: str
    conduit_id: UUID
    surface_id: UUID = NIL_SENTINEL_ID


@dataclass(frozen=True)
class ResolvedContext:
    """Every input the decision point resolved for the calling principal.

    The live request path. A decision reached with this context is the
    system's actual answer, and its `evaluated` set names every conjunct
    the gate consults.
    """

    policy: Policy


@dataclass(frozen=True)
class PolicyOnlyContext:
    """A hypothetical, where only the Policy conjunct is answerable.

    Carried by the query slices, which ask about a principal other than
    the caller, a policy other than the deployment's configured one, or
    both. The decision point cannot resolve the remaining conjuncts for
    a subject that is not making the request, so the answer it returns
    is necessary and not sufficient, and says so through `evaluated`.
    """

    policy: Policy


type DecisionContext = ResolvedContext | PolicyOnlyContext


def decide_authorization(
    request: AuthorizationRequest,
    context: DecisionContext,
) -> AuthzResult:
    """Reach the authorization decision for `request` under `context`.

    Returns `Allow` or `Deny`, each stamped with the conjuncts it
    consulted. The two context arms currently reach the same answer
    because the Policy is the only conjunct that exists; they are kept
    apart so that the next conjunct cannot be added to the live path
    without a decision about the hypothetical one.
    """
    match context:
        case ResolvedContext():
            return evaluate(
                context.policy,
                principal_id=request.principal_id,
                command_name=request.command_name,
                conduit_id=request.conduit_id,
                surface_id=request.surface_id,
            )
        case PolicyOnlyContext():
            return evaluate(
                context.policy,
                principal_id=request.principal_id,
                command_name=request.command_name,
                conduit_id=request.conduit_id,
                surface_id=request.surface_id,
            )
        case _:  # pragma: no cover - exhaustiveness guard
            assert_never(context)


__all__ = [
    "AuthorizationRequest",
    "DecisionContext",
    "PolicyOnlyContext",
    "ResolvedContext",
    "decide_authorization",
]

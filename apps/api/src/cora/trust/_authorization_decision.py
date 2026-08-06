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

## Why two context arms

They no longer carry the same fields: `ResolvedContext` holds the
liveness of the calling principal and `PolicyOnlyContext` cannot. That
divergence is the mechanism working, not drift. The arms exist so that
adding a conjunct is a question the author cannot avoid answering, and
liveness was the first one to actually ask it.

The answer it forced is worth recording, because the obvious reasoning
gives the wrong result. Liveness IS resolvable for a principal other
than the caller: it needs only their id, unlike a window, which needs
state the caller would have to assert. So the arm's original rule, that
a hypothetical cannot resolve the remaining conjuncts, does not apply.
It stays out anyway, for the second half of the rule: resolving it is
fine, ANSWERING with it discloses whether another principal has been
switched off, to anyone cleared to ask a hypothetical.

Merging the arms into one type with a nullable "resolved" flag would
return this to a runtime check that a future conjunct can silently skip,
in the same way the per-window authority types elsewhere in this bounded
context delete a forbidden-field error class by making the field
unrepresentable.

## Partiality is a return value, not a convention

Every result carries `evaluated`, the set of conjuncts actually
consulted. A query slice cannot forget to mark its answer partial,
because the same function that answered also reported what it skipped.
That is what makes "necessary but not sufficient" checkable at the call
site, in a log, and in a test, rather than a caveat in a docstring
somebody has to have read.
"""

from dataclasses import dataclass
from typing import Final, assert_never
from uuid import UUID

from cora.infrastructure.ports import (
    Allow,
    AuthzResult,
    Conjunct,
    Deny,
    PrincipalLiveness,
)
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.trust.aggregates.policy import Policy, evaluate

# Cause class plus the remedy the denied principal's operator can issue.
# The human-envelope design requires a denial to name both, because a
# refusal that says only "no" costs a beamtime shift to diagnose. No
# identifying detail beyond the cause: who the principal is belongs in
# the verdict logbook, not in a response body.
_LIVENESS_DENIAL: Final[dict[PrincipalLiveness, str]] = {
    PrincipalLiveness.DEACTIVATED: (
        "Principal is deactivated. Remedy: reactivate_actor (POST /actors/{actor_id}/reactivate)."
    ),
    PrincipalLiveness.UNREGISTERED: (
        "Principal is not a registered actor. Remedy: register_actor (POST /actors)."
    ),
}


def _liveness_denial(liveness: PrincipalLiveness) -> str:
    reason = _LIVENESS_DENIAL.get(liveness)
    if reason is None:  # pragma: no cover - ACTIVE never reaches here
        msg = f"no denial reason defined for liveness {liveness!r}"
        raise AssertionError(msg)
    return reason


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

    `liveness` is None whenever the conjunct did not run: the posture is
    "off" or "shadow", no lookup is wired, the command is exempt, or the
    read failed. It is never a permissive default standing in for a real
    ACTIVE answer, which is why the field is three-valued-or-absent
    rather than a bool.

    The absence shows up as `Conjunct.LIVENESS` missing from `evaluated`
    on the RESULT, and nowhere else: the `Verdict` entry row carries no
    conjunct column, so a reader of the verdict logbook cannot tell an
    unevaluated request from an enforced one.
    """

    policy: Policy
    liveness: PrincipalLiveness | None = None


@dataclass(frozen=True)
class PolicyOnlyContext:
    """A hypothetical, where only the Policy conjunct is answerable.

    Carried by the query slices, which ask about a principal other than
    the caller, a policy other than the deployment's configured one, or
    both. The decision point cannot resolve the remaining conjuncts for
    a subject that is not making the request, so the answer it returns
    is necessary and not sufficient, and says so through `evaluated`.

    Liveness is deliberately NOT carried here, and the reason is worth
    stating because it is the first conjunct where the arm's rule had to
    be applied rather than assumed. Unlike a window, liveness IS
    resolvable for a principal other than the caller: it needs only
    their id. It stays out because RESOLVING it is not the problem,
    ANSWERING with it is. "May Bob run this?" would start disclosing
    whether Bob has been deactivated, to any caller cleared to ask a
    hypothetical. That is exactly the leak this arm exists to prevent,
    so the honest answer stays "the Policy permits it, and I did not
    check whether Bob is switched on", carried by `evaluated`.
    """

    policy: Policy


type DecisionContext = ResolvedContext | PolicyOnlyContext


def decide_authorization(
    request: AuthorizationRequest,
    context: DecisionContext,
) -> AuthzResult:
    """Reach the authorization decision for `request` under `context`.

    Returns `Allow` or `Deny`, each stamped with the conjuncts it
    consulted.

    ## Policy is evaluated first, and that ordering is a disclosure rule

    A principal the Policy does not permit is refused on the Policy
    alone, and never learns whether it is also switched off. Checking
    liveness first would turn every gate into an oracle for "does this
    principal exist, and has an operator disabled it", answerable by
    anyone who can provoke a denial. So liveness narrows the set of
    already-permitted callers and nothing else, which is also why it can
    only ever turn an Allow into a Deny.
    """
    match context:
        case ResolvedContext():
            decision = evaluate(
                context.policy,
                principal_id=request.principal_id,
                command_name=request.command_name,
                conduit_id=request.conduit_id,
                surface_id=request.surface_id,
            )
            if context.liveness is None or isinstance(decision, Deny):
                return decision
            evaluated = decision.evaluated | {Conjunct.LIVENESS}
            if context.liveness is PrincipalLiveness.ACTIVE:
                return Allow(evaluated=evaluated)
            return Deny(reason=_liveness_denial(context.liveness), evaluated=evaluated)
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

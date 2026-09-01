"""Policy aggregate state, value objects, domain errors, and pure evaluation.

Per ISA-99, a Policy is an authorization rule attached to a specific
Conduit: it answers "may principal P issue command C via this
Conduit". The Policy aggregate's `evaluate` function is the pure
domain-level Policy Decision Point; the `TrustAuthorize` infra
adapter wires it behind the cross-BC `Authorize` port.

Policy is intentionally minimal:
  - `id` + `name`
  - `conduit_id` — the single Conduit this policy governs (one
    policy per conduit; cross-policy resolution is the
    `TrustAuthorize` adapter's problem)
  - `grants: frozenset[tuple[UUID, str]]` — explicit (principal,
    command) pairs. The command name matches the discriminator string
    used by the Authorize port and `event_type_name` everywhere else.

## Pairs, not two lists multiplied

`grants` holds PAIRS deliberately. The earlier shape was two
independent sets, `permitted_principal_ids` and `permitted_commands`,
and `evaluate` checked membership in each separately — which grants
every principal every command, the full N x M cross-product. A rulebook
listing a read-only status feed alongside a supervisor that may abort a
run granted the feed permission to abort runs. Nothing exercised that
authority, but the rulebook said more than the code it governed did,
and a rulebook that overstates is the one artifact that must not.

The two sets survive as DERIVED properties so existing readers keep
working; neither is stored, and neither can disagree with `grants`
because both are computed from it.

A frozenset in domain state (deduplicated, hashable, set-membership
in O(1) for `evaluate`); a sorted list of two-element arrays in event
payloads (JSON-friendly, deterministic). The evolver bridges the two.

A `PolicyDefined` written before pairs existed carries the two lists
and no `grants` key. `events.from_stored` cross-products them at the
deserialization boundary, so such a policy folds to exactly the
permissions it has always had — the same place, and the same reason,
that a legacy event's missing `surface_id` defaults there.

Status lifecycle (`Drafted → Approved → Active → Superseded`, per
BC-map) and modify/revoke slices defer to later sub-phases per the
same additive-state pattern as Zone and Conduit.

**No referential integrity at command time.** `conduit_id` and
each principal named in `grants` are stored as bare UUIDs
without verifying the referenced Conduits / Actors exist. Same
event-sourcing posture as Conduit→Zone: typos produce
"dangling" policies; downstream evaluation just denies because
the conduit_id mismatch surfaces at evaluate-time.

Empty `grants` is allowed and produces a deny-all policy by
construction (every evaluation hits the "not in {empty}" branch).
Useful for temporarily revoking access without deleting the policy.
"""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from cora.infrastructure.ports import Allow, AuthzResult, Conjunct, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.bounded_text import bounded_name
from cora.shared.text_bounds import REASON_MAX_LENGTH

POLICY_NAME_MAX_LENGTH = 200


class InvalidPolicyNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Policy name must be 1-{POLICY_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class PolicyAlreadyExistsError(Exception):
    """Attempted to define a policy whose stream already has events."""

    def __init__(self, policy_id: UUID) -> None:
        super().__init__(f"Policy {policy_id} already exists")
        self.policy_id = policy_id


class InvalidPolicySurfaceError(ValueError):
    """A new Policy must bind a real Surface; the nil sentinel is rejected.

    The nil `surface_id` sentinel survives only on the immutable V1
    bootstrap seed stream (folded by `from_stored`). New policies must
    bind a concrete Surface so `evaluate` can strict-match the arrival
    surface; a nil-surface policy denies every real-surface call.
    """

    def __init__(self) -> None:
        super().__init__(
            "Policy surface_id must bind a real Surface "
            "(the nil sentinel is reserved for the retired V1 fold)"
        )


class PolicyNotFoundError(Exception):
    """A transition (e.g. revoke_grant) targeted a Policy stream with no events."""

    def __init__(self, policy_id: UUID) -> None:
        super().__init__(f"Policy {policy_id} not found")
        self.policy_id = policy_id


class InvalidPolicyGrantRevokeReasonError(ValueError):
    """Reason text on revoke_grant is empty or too long after trim."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Policy grant-revoke reason must be 1-{REASON_MAX_LENGTH} chars "
            f"after trimming (got: {value!r})"
        )
        self.value = value


@bounded_name(max_length=POLICY_NAME_MAX_LENGTH, error_class=InvalidPolicyNameError)
@dataclass(frozen=True)
class PolicyName:
    """Display name for a policy. Trimmed; 1-200 chars.

    Uses the shared `@bounded_name` decorator from
    `cora.shared.bounded_text`.
    """

    value: str


@dataclass(frozen=True)
class Policy:
    """Aggregate root: an authorization rule attached to a Conduit + Surface pair.

    `surface_id`: the process-level arrival point this policy gates.
    `evaluate` strict-matches it against the call's arrival surface.
    The nil sentinel survives only on the immutable V1 bootstrap seed
    stream (folded by `from_stored`); such a policy strict-denies every
    real-surface call and is therefore operationally inert. The
    canonical bootstrap policy binds to the seeded HTTP Surface, and new
    policies must bind a concrete Surface (`define_policy` rejects nil).
    """

    id: UUID
    name: PolicyName
    conduit_id: UUID
    grants: frozenset[tuple[UUID, str]]
    surface_id: UUID = NIL_SENTINEL_ID

    @property
    def permitted_principal_ids(self) -> frozenset[UUID]:
        """Every principal this policy grants anything to.

        Derived, never stored. Answers "is this principal known here at
        all", which is what `revoke_grant` asks and what `evaluate` uses
        to pick between its two refusal reasons. It deliberately does
        NOT answer what that principal may do; `grants` does.

        O(len(grants)), recomputed on every read. Fine for the callers
        above, which read it once; do not put it inside a loop or on a
        per-request path. `evaluate` reads it only after a refusal is
        already certain, for exactly this reason.
        """
        return frozenset(principal_id for principal_id, _ in self.grants)

    @property
    def permitted_commands(self) -> frozenset[str]:
        """Every command this policy grants to SOMEONE.

        Derived, never stored. This is a UNION across principals, not a
        per-principal answer: a command appearing here means at least
        one principal may issue it, never that any given principal may.
        Callers narrowing to one principal must go through `evaluate`
        (or `decide_authorization`), which consults the pair.

        O(len(grants)), recomputed on every read; see the sibling
        property. `list_permissions` reads it once to get its candidate
        set and then asks the real decision per candidate, which is the
        intended shape.
        """
        return frozenset(command_name for _, command_name in self.grants)


_POLICY_EVALUATED: Final[frozenset[Conjunct]] = frozenset({Conjunct.POLICY})


def evaluate(
    policy: Policy,
    *,
    principal_id: UUID,
    command_name: str,
    conduit_id: UUID,
    surface_id: UUID = NIL_SENTINEL_ID,
) -> AuthzResult:
    """Pure Policy Decision Point: does `policy` permit (principal, command, conduit, surface)?

    Returns `Allow()` or `Deny(reason=...)`. The reason string is
    diagnostic — meant to flow into structlog / API responses for
    debugging, not for end-user display. Check order is cheapest-
    first: conduit mismatch → surface mismatch → principal not in
    set → command not in set.

    Surface matching is strict equality. A policy that folded to a nil
    `surface_id` (the immutable V1 bootstrap seed is the only such
    stream) never matches a real arrival surface, so it strict-denies
    every live call and is operationally inert. The nil-as-wildcard
    legacy-fold shim was removed once the V1 bootstrap policy was
    retired in favor of the surface-bound bootstrap policy; new
    policies must bind a concrete Surface (`define_policy` rejects nil
    via `InvalidPolicySurfaceError`).

    Living in `state.py` because it's a pure operation on Policy
    state (no I/O, no awaits, no mutation).
    """
    if conduit_id != policy.conduit_id:
        return Deny(
            reason=(f"Policy {policy.id} governs conduit {policy.conduit_id}, not {conduit_id}"),
            evaluated=_POLICY_EVALUATED,
        )
    if surface_id != policy.surface_id:
        return Deny(
            reason=(f"Policy {policy.id} governs surface {policy.surface_id}, not {surface_id}"),
            evaluated=_POLICY_EVALUATED,
        )
    # One hash lookup settles the permitted case, which is the case
    # every served request takes. Deciding WHICH refusal to report needs
    # `permitted_principal_ids`, and that property is O(len(grants)):
    # it rebuilds a set from every pair each time it is read. Asking it
    # first, as the two-set version could afford to, put that scan on
    # the hot path and made a 64-principal policy measurably slower per
    # decision (caught by the authz-latency benchmark, not by review).
    # Refusals pay it instead, where an extra microsecond is free beside
    # the logging and Verdict write that follow.
    if (principal_id, command_name) in policy.grants:
        return Allow(evaluated=_POLICY_EVALUATED)
    if principal_id not in policy.permitted_principal_ids:
        return Deny(
            reason=f"Principal {principal_id} not in policy {policy.id}'s permitted set",
            evaluated=_POLICY_EVALUATED,
        )
    # The principal IS granted something here, just not this. The reason
    # names it because the same command may well be permitted to a
    # different principal under this very policy, and a reader who saw
    # only the command name would reasonably conclude the policy forbids
    # it outright.
    return Deny(
        reason=(
            f"Command {command_name!r} not granted to principal "
            f"{principal_id} by policy {policy.id}"
        ),
        evaluated=_POLICY_EVALUATED,
    )

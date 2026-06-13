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
  - `permitted_principal_ids: frozenset[UUID]` — explicit allow-list
  - `permitted_commands: frozenset[str]` — command-name allow-list
    (matches the discriminator string used by the Authorize port and
    the `event_type_name` everywhere else)

Frozensets in domain state (deduplicated, hashable, set-membership
in O(1) for `evaluate`); plain lists in event payloads (JSON-friendly,
sorted for determinism). The evolver bridges the two.

Status lifecycle (`Drafted → Approved → Active → Superseded`, per
BC-map) and modify/revoke slices defer to later sub-phases per the
same additive-state pattern as Zone and Conduit.

**No referential integrity at command time.** `conduit_id` and
each entry in `permitted_principal_ids` are stored as bare UUIDs
without verifying the referenced Conduits / Actors exist. Same
event-sourcing posture as Conduit→Zone: typos produce
"dangling" policies; downstream evaluation just denies because
the conduit_id mismatch surfaces at evaluate-time.

Empty `permitted_principal_ids` or empty `permitted_commands` is
allowed and produces a deny-all policy by construction (every
evaluation hits the "not in {empty}" branch). Useful for
temporarily revoking access without deleting the policy.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.infrastructure.ports import Allow, AuthzResult, Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.bounded_text import bounded_name

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
    permitted_principal_ids: frozenset[UUID]
    permitted_commands: frozenset[str]
    surface_id: UUID = NIL_SENTINEL_ID


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
            reason=(f"Policy {policy.id} governs conduit {policy.conduit_id}, not {conduit_id}")
        )
    if surface_id != policy.surface_id:
        return Deny(
            reason=(f"Policy {policy.id} governs surface {policy.surface_id}, not {surface_id}")
        )
    if principal_id not in policy.permitted_principal_ids:
        return Deny(reason=f"Principal {principal_id} not in policy {policy.id}'s permitted set")
    if command_name not in policy.permitted_commands:
        return Deny(reason=(f"Command {command_name!r} not in policy {policy.id}'s permitted set"))
    return Allow()

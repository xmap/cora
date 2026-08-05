"""The `ListPermissions` query — enumerate a Policy's permitted commands for a principal.

Asks "given Policy P, what commands can `evaluated_principal_id`
execute via `evaluated_conduit_id`?". Returns a sorted list of
permitted command names, the surface that list is scoped to, plus an
`incomplete: bool` flag (always False at v1; required from day 1 per
the design lock anti-hook (future ABAC policies may make enumeration
lossy).

The surface is not asked for, it is reported. A Policy binds exactly
one surface and matches it by strict equality, so the surface is a
property of the Policy rather than a free variable the caller chooses,
and the answer names it instead of taking it.

Field naming mirrors `evaluate_policy.EvaluatePolicy` (the
`evaluated_*` prefix disambiguates from the caller's `principal_id`
handler kwarg).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ListPermissions:
    """Enumerate a Policy's permitted commands for (principal, conduit)."""

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_conduit_id: UUID


@dataclass(frozen=True)
class PermissionListing:
    """The enumerate result.

    `permitted_commands` is sorted alphabetically and holds exactly the
    commands the shared authorization decision permits, so the listing
    cannot disagree with the gate about what this Policy allows.

    `surface_id` is the arrival surface the listing is scoped to, and it
    is why the listing is trustworthy rather than merely suggestive. A
    Policy matches its surface by strict equality, so it permits nothing
    at all on any other surface. Reporting the set without naming the
    surface invited the reader to assume it held everywhere, which was
    wrong for every request arriving elsewhere: the same principal and
    the same command would be listed as permitted and denied in the
    same breath. Reading `permitted_commands` without reading
    `surface_id` is reading half the answer.

    `incomplete: bool` is always False at v1; required for forward
    compat with ABAC/conditional policies.
    """

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_conduit_id: UUID
    surface_id: UUID
    permitted_commands: list[str]
    incomplete: bool

"""The `EvaluatePolicy` query — intent dataclass for this read slice.

Asks "does Policy P permit `evaluated_principal_id` to issue
`evaluated_command_name` via `evaluated_conduit_id`?". The handler loads
the Policy via `load_policy` and delegates to the pure
`evaluate(policy, ...)` function in the aggregate.

Field naming: `evaluated_*` prefix disambiguates WHAT'S BEING
EVALUATED against the policy from the CALLER making the query (the
caller arrives via the cross-BC `principal_id` handler kwarg).
Without the prefix, `query.principal_id` and the handler's
`principal_id` kwarg would share a name with different meaning at
every handler call site. (Originally named `subject_*`; renamed
2026-05 because "subject" overloaded with the Subject BC. The
`evaluated_*` form has no such overload.)
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EvaluatePolicy:
    """Evaluate a Policy against a (principal, command, conduit, surface) tuple."""

    policy_id: UUID
    evaluated_principal_id: UUID
    evaluated_command_name: str
    evaluated_conduit_id: UUID
    evaluated_surface_id: UUID

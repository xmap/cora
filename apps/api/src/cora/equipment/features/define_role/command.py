"""The `DefineRole` command -- intent dataclass for this slice.

Carries the caller's contract content: display name, docstring, and
the four sets (required_affordances, optional_affordances, produces,
consumes). Server-side concerns (new aggregate id, wall-clock
timestamp, correlation id, per-event ids) are injected by the handler
from infrastructure ports.

`required_affordances` MAY be empty for documentation-only Role
shapes; the decider does not reject empty required-sets at 3A (the
Conditioner-degeneracy concern that drove Q3 to defer the seed
Conditioner does NOT block ad-hoc empty-required Roles when an
operator explicitly authors one). `optional_affordances` MAY be
empty. The two sets MUST be disjoint
(`RoleAffordanceOverlapError`).

`produces` and `consumes` are open SignalType vocabularies; each
entry is trim-and-bound-checked at the decider (50-char max per
`SIGNAL_TYPE_MAX_LENGTH`). Empty sets are accepted.

`docstring` is required (non-empty) so operators picking among Roles
at Method-authoring time see the contract intent without spelunking
through code (`InvalidRoleDocstringError` on empty / whitespace-only).
"""

from dataclasses import dataclass

from cora.equipment.aggregates.family import Affordance


@dataclass(frozen=True)
class DefineRole:
    """Define a new global Role contract."""

    name: str
    docstring: str
    required_affordances: frozenset[Affordance]
    optional_affordances: frozenset[Affordance]
    produces: frozenset[str]
    consumes: frozenset[str]

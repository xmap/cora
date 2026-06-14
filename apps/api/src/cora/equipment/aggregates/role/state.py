"""Role aggregate state, errors, and value objects.

`Role` is the Equipment BC's global functional binding contract: WHAT
operational shape a Method needs (`Detector`, `Positioner`, `Controller`,
`Sensor`) without pinning the anatomical Family that provides it.
Per [[project-role-aggregate-design]] Lock 1, Role is a sister
aggregate to Family, NOT a kind of Family: separate registry, separate
events, separate identifier (`RoleId`).

## Aggregate scope (Layer 3 sub-slice 3A)

Lightweight contract only (Lock 2): `required_affordances` +
`optional_affordances` + `produces` + `consumes` + `docstring`. No
`settings_schema`, no instances, no ports. Role is templated, not
instantiated: a Family or Assembly declares it satisfies a Role via
`presents_as: frozenset[RoleId]` (3B / 3C), and a Method binds a
positional role slot to a Role via `RoleRequirement.role_kind: UUID`
(3D). The Plan-side satisfaction check at `bind_plan_role` walks
`Family.presents_as` and requires the Family's `affordances` superset
the Role's `required_affordances` (ANY-single-family
disjunction for multi-Family Assets).

## No FSM at 3A (Q1 user pick, 2026-06-10)

3A ships ONE event (`RoleDefined`); update events
(`RoleAffordancesUpdated`, `RoleSignalsUpdated`) are deferred until
the Lock 14 SiLA-2 FQN-terminal-major versioning trigger fires (first
`required_affordances` change that breaks an existing Asset's
satisfaction). Shipping update events at 3A would lock the SHAPE of
versioning before the trigger fires, which is exactly what Lock 14
defers. No `RoleStatus` enum at this slice; status is implicit
(`Defined`) on every Role until versioning lands.

## Bounded-name VO

`RoleName` follows the trimmed-bounded-name VO pattern; uses the
shared `validate_bounded_text` helper. NewType `RoleId` lives at
`cora/equipment/aggregates/_value_types.py` (CredentialId precedent
from Slice 6; keeps the fold-symmetry test's attribution-NewType
allowlist clean).

## RoleName vs RoleKindName terminology note

The Method-local positional label (slice 1, shipped) is the per-Method
operator handle, e.g. `DETECTOR`, `SAMPLE_MONITOR`. The global Role
contract's display name (this aggregate) is also called `RoleName` in
the codebase; the design memo uses `RoleKindName` to disambiguate in
prose. The two are distinct concepts at distinct layers (Method-local
vs global registry) but the slice-1 `RoleName` type already lives in
the Recipe BC under `cora.recipe.aggregates.method`, so the global
contract's name is wrapped here as `RoleName` without name collision
(no cross-BC import). Cross-BC consumers grep on the qualified import
path to disambiguate.
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.role._signal_type import SignalType
from cora.shared.bounded_text import bounded_name

ROLE_NAME_MAX_LENGTH = 200
ROLE_DOCSTRING_MAX_LENGTH = 2000


class InvalidRoleNameError(ValueError):
    """The supplied role name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Role name must be 1-{ROLE_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class InvalidRoleDocstringError(ValueError):
    """The supplied docstring is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Role docstring must be 1-{ROLE_DOCSTRING_MAX_LENGTH} chars after "
            f"trimming (got length {len(value)})"
        )
        self.value = value


class RoleAlreadyExistsError(Exception):
    """Attempted to define a Role whose stream already has events."""

    def __init__(self, role_id: UUID) -> None:
        super().__init__(f"Role {role_id} already exists")
        self.role_id = role_id


class RoleNotFoundError(Exception):
    """Attempted an operation on a Role whose stream has no events."""

    def __init__(self, role_id: UUID) -> None:
        super().__init__(f"Role {role_id} not found")
        self.role_id = role_id


class RoleAffordanceOverlapError(ValueError):
    """`required_affordances` and `optional_affordances` are not disjoint.

    A Role's required and optional Affordance sets MUST be disjoint:
    "optional" is meaningful only as a strictly-stronger contract than
    "required absent", and listing the same Affordance in both sets
    signals operator confusion. Caught at decider time.
    """

    def __init__(self, role_id: UUID, overlap: frozenset[Affordance]) -> None:
        super().__init__(
            f"Role {role_id} has Affordances appearing in both required and "
            f"optional sets: {sorted(a.value for a in overlap)!r}"
        )
        self.role_id = role_id
        self.overlap = overlap


@bounded_name(max_length=ROLE_NAME_MAX_LENGTH, error_class=InvalidRoleNameError)
@dataclass(frozen=True)
class RoleName:
    """Display name for a Role. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class Role:
    """Aggregate root: a global functional binding contract.

    `required_affordances` lists Affordances every satisfying Family
    MUST advertise. `optional_affordances` lists Affordances a Family
    MAY advertise to satisfy a stronger variant of the same Role
    (Method consumers gate on optional independently). The two sets
    are disjoint (`RoleAffordanceOverlapError` at decider time).

    `produces` and `consumes` declare the SignalType vocabulary
    satisfying Assets emit (out ports) and accept (in ports). Used by
    Plan-side wiring guidance (informative at 3A; the bind_plan_role
    satisfaction check in 3D gates on `presents_as` + affordances
    superset, not on signal types).

    `docstring` is the operator-readable one-paragraph contract
    explanation. Required (non-empty) so operators picking among Roles
    at Method-authoring time see the contract intent without spelunking
    through code.
    """

    id: RoleId
    name: RoleName
    docstring: str
    required_affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])
    optional_affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])
    produces: frozenset[SignalType] = field(default_factory=frozenset[SignalType])
    consumes: frozenset[SignalType] = field(default_factory=frozenset[SignalType])

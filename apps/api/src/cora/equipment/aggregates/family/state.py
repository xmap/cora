"""Family aggregate state, status enum, errors, and value objects.

`Family` is the device-class abstraction: WHAT kind of equipment this is,
device-agnostic. Examples: "RotaryStage", "LinearStage", "Camera",
"Scintillator", "Hexapod", "Mirror", "TimingController". Referenced by
`Asset.family_ids` to declare what classes a Device belongs to, and by
`Method.needed_family_ids` to express a Method's hardware contract;
resolved at `Plan` binding when the contract is matched against
specific `Asset` instances.

## Aggregate scope

Family is the Equipment BC's device-class aggregate. Same FSM
(Defined to Versioned to Deprecated), with `settings_schema` and
`affordances` as the two declarative fields.

`affordances: frozenset[Affordance]` is REQUIRED at
`define_family` time. Empty `frozenset()` is a valid argument the
caller must supply explicitly (Scintillator's case at v1, until the
Consumable lifecycle affordance makes it non-empty). Affordance set
changes flow through `version_family` (a new version IS a new
declaration; matches Method/Plan/Practice replace-on-version
precedent), NOT a separate `set_family_affordances` slice.

The word "Capability" is reserved for the Recipe BC operations-layer
aggregate (see [[project-capability-aggregate-design]]) and must not
appear in Equipment BC.

## Status as enum-in-state, derived-from-event-type-in-evolver

`FamilyStatus` is a `StrEnum` so the values would serialize naturally
as JSON-friendly strings IF carried in an event payload. Today they
aren't: state holds the enum (typed) and the evolver derives the new
status from the event TYPE — same precedent as `SubjectStatus` /
`ActorDeactivated → active=False`.

## Why Family lives in Equipment (not its own BC)

Per the BC map, Family is one of two aggregates in the Equipment BC
(the other is Asset). Family ships first because it's standalone (no
cross-aggregate refs to other Equipment aggregates) and unblocks
Method's `needed_family_ids` contract.

## Bounded-name VO

`FamilyName` follows the trimmed-bounded-name VO pattern; uses the
shared `validate_bounded_text` helper.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family.affordance import Affordance
from cora.shared.bounded_text import bounded_name

FAMILY_NAME_MAX_LENGTH = 200
FAMILY_VERSION_TAG_MAX_LENGTH = 50


class FamilyStatus(StrEnum):
    """The Family's lifecycle state.

    Transitions:
      - Defined -> Versioned        (version_family)
      - (Defined | Versioned) -> Deprecated   (deprecate_family)

    `Defined` is the genesis state set by `define_family`. The enum
    values are PascalCase strings (matching the BC-map status
    vocabulary) so log lines and DTOs read naturally without
    additional mapping.
    """

    DEFINED = "Defined"
    VERSIONED = "Versioned"
    DEPRECATED = "Deprecated"


class InvalidFamilyNameError(ValueError):
    """The supplied name is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Family name must be 1-{FAMILY_NAME_MAX_LENGTH} chars after trimming (got: {value!r})"
        )
        self.value = value


class FamilyAlreadyExistsError(Exception):
    """Attempted to define a family whose stream already has events."""

    def __init__(self, family_id: UUID) -> None:
        super().__init__(f"Family {family_id} already exists")
        self.family_id = family_id


class FamilyNotFoundError(Exception):
    """Attempted an operation on a family whose stream has no events."""

    def __init__(self, family_id: UUID) -> None:
        super().__init__(f"Family {family_id} not found")
        self.family_id = family_id


class FamilyCannotVersionError(Exception):
    """Attempted to version a family not in `Defined` or `Versioned`.

    Multi-source guard: `version_family` accepts both `Defined` and
    `Versioned`. Only `Deprecated` is rejected (you can't revise a
    deprecated family — un-deprecate first if you want to bring it
    back, though that slice doesn't exist today).
    """

    def __init__(self, family_id: UUID, current_status: "FamilyStatus") -> None:
        super().__init__(
            f"Family {family_id} cannot be versioned: currently in status "
            f"{current_status.value}, version requires "
            f"{FamilyStatus.DEFINED.value} or {FamilyStatus.VERSIONED.value}"
        )
        self.family_id = family_id
        self.current_status = current_status


class FamilyCannotDeprecateError(Exception):
    """Attempted to deprecate a family not in `Defined` or `Versioned`."""

    def __init__(self, family_id: UUID, current_status: "FamilyStatus") -> None:
        super().__init__(
            f"Family {family_id} cannot be deprecated: currently in status "
            f"{current_status.value}, deprecate requires "
            f"{FamilyStatus.DEFINED.value} or {FamilyStatus.VERSIONED.value}"
        )
        self.family_id = family_id
        self.current_status = current_status


class InvalidFamilyVersionTagError(ValueError):
    """The supplied version tag is empty, whitespace-only, or too long."""

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Family version tag must be 1-{FAMILY_VERSION_TAG_MAX_LENGTH} "
            f"chars after trimming (got: {value!r})"
        )
        self.value = value


class FamilyCannotPresentAsError(Exception):
    """Family cannot present the requested Role.

    Raised by `add_family_presents_as` when the requested Role's
    `required_affordances` is not a subset of the Family's current
    `affordances`. Per Lock 17 ANY-single-family disjunction, a Family
    that does not cover the Role's required Affordances cannot
    advertise the role, regardless of what other Families on the
    same Asset may cover.

    Taxonomy: `<X>Cannot<Verb>Error` (mirrors `FamilyCannotVersionError`
    + `FamilyCannotDeprecateError`); the verb is "PresentAs" (the
    add/remove pair operates on the presents_as set).
    """

    def __init__(
        self,
        family_id: UUID,
        role_id: UUID,
        missing_affordances: frozenset[Affordance],
    ) -> None:
        super().__init__(
            f"Family {family_id} cannot present as Role {role_id}: "
            f"missing required Affordances "
            f"{sorted(a.value for a in missing_affordances)!r} "
            "(Family.affordances must superset Role.required_affordances)"
        )
        self.family_id = family_id
        self.role_id = role_id
        self.missing_affordances = missing_affordances


class FamilyRolePresentsAsAlreadyError(Exception):
    """`role_id` is already present in the Family's `presents_as` set.

    Strict-not-idempotent: re-adding the same Role surfaces this
    rather than no-op. Mirrors `add_asset_family` /
    `add_method_required_role` precedent.
    """

    def __init__(self, family_id: UUID, role_id: UUID) -> None:
        super().__init__(
            f"Family {family_id} already presents as Role {role_id} (strict-not-idempotent)"
        )
        self.family_id = family_id
        self.role_id = role_id


class FamilyRolePresentsAsNotPresentError(Exception):
    """`role_id` is not in the Family's `presents_as` set.

    Strict-not-idempotent: removing a Role the Family does not
    advertise surfaces this rather than no-op. Mirrors
    `remove_asset_family` / `remove_method_required_role` precedent.
    """

    def __init__(self, family_id: UUID, role_id: UUID) -> None:
        super().__init__(
            f"Family {family_id} does not present as Role {role_id} "
            "(strict-not-idempotent on remove)"
        )
        self.family_id = family_id
        self.role_id = role_id


@bounded_name(max_length=FAMILY_NAME_MAX_LENGTH, error_class=InvalidFamilyNameError)
@dataclass(frozen=True)
class FamilyName:
    """Display name for a family. Trimmed; 1-200 chars."""

    value: str


@dataclass(frozen=True)
class Family:
    """Aggregate root: a device-class family definition.

    `version` is the operator-supplied label of the most recent
    `version_family` call (None until first version). State always
    holds the latest tag — past tags live in the event stream as
    `FamilyVersioned` events.

    `affordances` is the closed-enum set of device-level operational
    primitives this Family supports (5j). Required at `define_family`
    time; empty `frozenset()` is a valid argument when no v1 Affordance
    applies (Scintillator's case). Replaced wholesale by
    `version_family` (a new version IS a new declaration). See
    `cora.equipment.aggregates.family.affordance.Affordance` for the
    28-item closed enum and the 3-pattern rule.

    `settings_schema` is the optional JSON Schema (Draft 2020-12,
    constrained subset) declaring the shape of `Asset.settings` keys
    this Family "owns".

    `presents_as` is the set of global Role contracts this Family
    advertises (Layer 3 sub-slice 3B; see
    [[project-role-aggregate-design]] Lock 4 universal
    `Family.presents_as`). Direct-detection Camera Families advertise
    `{Detector}`; LinearStage / RotaryStage / Hexapod advertise
    `{Positioner}`; the empty-Affordances <Domain>Controller leaves
    advertise `{Controller}`. Added incrementally via
    `add_family_presents_as` (strict-not-idempotent; validates that
    `Family.affordances` supersets the Role's `required_affordances`);
    removed via `remove_family_presents_as`. PRESERVED across
    `version_family`, `deprecate_family`, and
    `update_family_settings_schema` (orthogonal-axis: matches
    `settings_schema` preservation precedent).
    """

    id: UUID
    name: FamilyName
    status: FamilyStatus = FamilyStatus.DEFINED
    version: str | None = None
    affordances: frozenset[Affordance] = field(default_factory=frozenset[Affordance])
    settings_schema: dict[str, Any] | None = field(default=None)
    presents_as: frozenset[RoleId] = field(default_factory=frozenset[RoleId])

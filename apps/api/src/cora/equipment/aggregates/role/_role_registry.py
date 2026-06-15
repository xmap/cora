"""Seed Role registry: the four closed-core Roles available at lifespan.

Per [[project-role-aggregate-design]] sub-slice 3A:
- 4 Roles ship as the closed-core registry: Detector, Positioner,
  Controller, Sensor.
- Conditioner is DEFERRED per Q3 (2026-06-10 user pick): no Affordance
  is universally required across Attenuators / Shutters / Mirrors, so
  the required-set would be vacuous, degenerating the Role to a tag.
  Rule-of-three trigger gates a future definition.

These constants do NOT register events at module import. Seeding
is performed via direct-append at scenario-fixture / lifespan-hook
time (mirroring the FacilityCode.SELF_FACILITY pattern from Slice 5).
The constants here are operator-readable identifiers + the
contractual content; the registration ceremony lives downstream.

## RoleId stability

`RoleId` values are UUID5-derived from a fixed namespace so the same
Role gets the same id across deployments. Federation-portability
(post-Layer-4 cross-facility catalog) requires this: a Method
authored at APS 2-BM that binds `role_kind=Detector` must resolve to
the same Detector UUID when shipped to MAX IV or DLS for execution.

The namespace UUID is derived from `uuid5(NAMESPACE_DNS, 'cora.role')`
once at lock-time and hardcoded so re-derivation is deterministic
without re-running the seed. Operators verifying the derivation can
recompute it from the same string seed.

The per-Role stream_id derivation `role_stream_id(name)` lower-cases
`name.value` before uuid5 so the deterministic id matches the
projection's `UNIQUE INDEX (LOWER(name))` constraint. A
`define_role` call with `name="detector"` and the SEED constant
`SEED_ROLE_DETECTOR_ID` (derived from `Detector`) collide on the same
stream, surfacing as `ConcurrencyError` at the event store before
the projection writer.

## Contract content

Each seed Role's `required_affordances`, `produces`, and `consumes`
are operator-facing claims about what satisfying Assets must declare.
The bind_plan_role satisfaction check (3D) walks Family.presents_as
and requires the Family's `affordances` superset the Role's
`required_affordances`. `produces` / `consumes` are open SignalType
vocabularies (informative at 3A; gating arrives at Layer-4 wire
guidance).

Docstrings are kept terse and operator-readable.
"""

import unicodedata
from typing import Final
from uuid import UUID, uuid5

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.role._signal_type import SignalType
from cora.equipment.aggregates.role.state import Role, RoleName

# Fixed UUID5 namespace for Role ids. Generated once at lock-time
# (2026-06-10 Layer-3 sub-slice 3A) as
# `uuid5(NAMESPACE_DNS, 'cora.role')`. Hardcoded so re-derivation is
# deterministic without requiring the uuid library at runtime in the
# seed path (operator-facing tooling can recompute it from the same
# string seed to verify).
_ROLE_NAMESPACE: Final[UUID] = UUID("d22027f6-9667-5f9f-bab9-5775f0aa70c4")


def role_stream_id(name: RoleName) -> RoleId:
    """Derive the deterministic stream_id for a Role from its name.

    NFC-normalizes then lower-cases `name.value` so the derivation
    matches the projection's `UNIQUE INDEX (LOWER(name))` rule and so
    composed vs decomposed Unicode spelling cannot fork identity: a
    `define_role` race on the same case-insensitive name collides on
    `expected_version=0` at the event store before the projection
    writer can crash. Mirrors `family_stream_id` / `model_stream_id`.
    """
    return RoleId(uuid5(_ROLE_NAMESPACE, unicodedata.normalize("NFC", name.value).lower()))


SEED_ROLE_DETECTOR_ID: Final[RoleId] = role_stream_id(RoleName("Detector"))
SEED_ROLE_POSITIONER_ID: Final[RoleId] = role_stream_id(RoleName("Positioner"))
SEED_ROLE_CONTROLLER_ID: Final[RoleId] = role_stream_id(RoleName("Controller"))
SEED_ROLE_SENSOR_ID: Final[RoleId] = role_stream_id(RoleName("Sensor"))


DETECTOR: Final[Role] = Role(
    id=SEED_ROLE_DETECTOR_ID,
    name=RoleName("Detector"),
    docstring=(
        "Acquires 2D image frames on exposure or trigger. Satisfying Assets "
        "or composed Assemblies emit Image / Frame signals. Direct-detection "
        "Cameras and composed scintillator-relay Assemblies both satisfy this "
        "Role; the multi-Family disjunction accepts either path."
    ),
    required_affordances=frozenset({Affordance.IMAGEABLE}),
    optional_affordances=frozenset(
        {Affordance.BINNABLE, Affordance.COOLABLE, Affordance.TRIGGERABLE, Affordance.STREAMABLE}
    ),
    produces=frozenset({SignalType("Image"), SignalType("Frame")}),
    consumes=frozenset({SignalType("TriggerIn")}),
)


POSITIONER: Final[Role] = Role(
    id=SEED_ROLE_POSITIONER_ID,
    name=RoleName("Positioner"),
    docstring=(
        "Drives at least one degree of freedom to operator-commanded positions. "
        "Satisfying Families include LinearStage, RotaryStage, Hexapod, and "
        "indexable mechanisms. Single-axis and multi-axis Assets both satisfy; "
        "the contract is positioning capability, not axis count."
    ),
    required_affordances=frozenset({Affordance.HOMEABLE, Affordance.LIMITABLE}),
    optional_affordances=frozenset(
        {
            Affordance.ROTATABLE,
            Affordance.TRANSLATABLE,
            Affordance.POSABLE,
            Affordance.INDEXABLE,
            Affordance.CAPTURABLE,
            Affordance.LEADING,
            Affordance.FOLLOWING,
        }
    ),
    produces=frozenset({SignalType("EncoderPosition")}),
    consumes=frozenset({SignalType("PositionCommand")}),
)


CONTROLLER: Final[Role] = Role(
    id=SEED_ROLE_CONTROLLER_ID,
    name=RoleName("Controller"),
    docstring=(
        "Generates or routes signals (motion, timing) that govern subordinate "
        "Assets. Satisfying Families are the empty-Affordances "
        "<Domain>Controller leaves (MotionController, TimingController). The "
        "Controller does NOT itself perform motion / imaging; subordinate "
        "Assets do, under its supervision."
    ),
    required_affordances=frozenset({Affordance.IDENTIFIABLE}),
    optional_affordances=frozenset({Affordance.REPORTABLE, Affordance.PULSING}),
    produces=frozenset({SignalType("ControlOut")}),
    consumes=frozenset({SignalType("ControlIn")}),
)


SENSOR: Final[Role] = Role(
    id=SEED_ROLE_SENSOR_ID,
    name=RoleName("Sensor"),
    docstring=(
        "Reports a continuous or discrete measurement on query or trigger. "
        "Satisfying Families include ion chambers, photodiodes, thermocouples, "
        "and other point-sensor anatomies. Distinct from Detector: a Sensor "
        "produces a scalar or short-vector Reading, not a 2D frame."
    ),
    required_affordances=frozenset({Affordance.REPORTABLE}),
    optional_affordances=frozenset({Affordance.TRIGGERABLE, Affordance.STREAMABLE}),
    produces=frozenset({SignalType("Reading")}),
    consumes=frozenset({SignalType("TriggerIn")}),
)


SEED_ROLES: Final[tuple[Role, ...]] = (
    DETECTOR,
    POSITIONER,
    CONTROLLER,
    SENSOR,
)


__all__ = [
    "CONTROLLER",
    "DETECTOR",
    "POSITIONER",
    "SEED_ROLES",
    "SEED_ROLE_CONTROLLER_ID",
    "SEED_ROLE_DETECTOR_ID",
    "SEED_ROLE_POSITIONER_ID",
    "SEED_ROLE_SENSOR_ID",
    "SENSOR",
    "role_stream_id",
]

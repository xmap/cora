"""Placement value object: where a Mount or Frame sits in space.

A Placement is the complete answer to "where is this thing and how
is it oriented?" It is a flat 6-degrees-of-freedom pose (three
position axes + three rotation axes) plus three additional pieces
of information that make the pose interpretable across surveys and
re-installations:

  - `parent_frame_id`: which coordinate frame the values are measured
    against (the 1.35 mrad standard beam centerline, an alternate
    centerline at the mirror, the optical-bench frame on a table, ...).
  - `reference_surface`: which physical feature of the part the
    position values were measured from (the upstream face of the
    thermal block, the center of the optic, the upstream face of the
    shielding). Without this, "z = 259313" is ambiguous.
  - `units`: the unit system the values are stored in. CORA stores
    canonically; conversion happens at the edge per
    `project_units_design.md`.

Tolerances are bilateral (symmetric ±) per axis. Per-axis tolerance
must be non-negative; zero means "exact." Asymmetric, projected,
MMC/LMC, and zone-shaped tolerances per ISO 1101 / ASME Y14.5 are
deferred (Watch item in `project_mount_frame_design.md`).

Flat 6-DoF is the v1 shape; the IFC `IfcLocalPlacement` is its
ancestor (parent-pointer + relative orientation). Promote to a
NeXus NXtransformations-style ordered axis-chain only when
articulated multi-DoF kinematics surface (Watch item).

`ReferenceSurface` is a closed StrEnum of four values; escape hatch
fires when a second facility lands and a new convention surfaces, OR
when a new component-category cohort at the existing facility has no
plausible fit among current values AND no canonical term in the
modeling-refs corpus (ISO 1101, ASME Y14.5, NeXus, AAS Hierarchical
Structures, OPC UA DI/LADS) would be a better fit. NOT a GD&T datum
(which is the derived theoretical entity); these are "datum features"
in GD&T parlance. CORA uses the longer `ReferenceSurface` to avoid
the term collision.

`UnitSystem` is a StrEnum with one v1 value (`SI_MM_RAD`):
millimetres for translation, radians for rotation. Extensible when
non-SI deployments land.

`Placement` is a closed-shape typed frozen dataclass. NOT
`json_schema_validation` (that pattern is for declarer-owns-schema /
carrier-owns-dict); validation lives in field shape + enum
membership + `__post_init__` checks.
"""

import math
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class InvalidPlacementError(ValueError):
    """A Placement failed VO-level domain validation.

    Failure modes at the VO layer:
      - Any tolerance is negative (tolerances are bilateral; zero
        means "exact", negative is meaningless).

    Cross-aggregate validations (parent_frame_id must reference an
    active Frame, etc.) happen at the handler / decider layer, not
    in the VO. Per the design memo: the VO is closed-shape; the
    handler is where cross-aggregate preconditions land.

    `reason` names the offending axis for diagnostics; the route
    layer's `_handle_validation_error` reads `str(exc)` (which
    formats as "Invalid Placement: <reason>"), so the reason is
    embedded in the message that surfaces in the 400 body.

    Lives in this module (an aggregate-scoped private VO module) so
    aggregate state.py / events.py can import without violating the
    aggregates-don't-depend-on-BC-root tach layering rule. The
    `test_no_domain_errors_outside_aggregate_or_errors_module`
    fitness exempts the entire `cora/<bc>/aggregates/...` subtree.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid Placement: {reason}")
        self.reason = reason


class ReferenceSurface(StrEnum):
    """The physical feature of a part that a Placement is measured FROM.

    Closed enum; CORA precedent is the Affordance StrEnum. Widening
    rules and GD&T-term-collision rationale live in the module docstring.
    """

    THERMAL_FACE = "ThermalFace"
    """Upstream face of the thermal component (front-end masks, beam stops,
    photon stops, Be windows; OFHC Cu / Be sit between cooling water and beam)."""
    OPTIC_CENTER = "OpticCenter"
    """Center of the optic (mirror axis, monochromator crystal axis;
    the active surface, not a face)."""
    SHIELDING_FACE = "ShieldingFace"
    """Upstream face of the shielding material (collimators, baffles;
    the W or Pb absorbing surface)."""
    MOUNTING_FACE = "MountingFace"
    """Precision-machined surface used to attach a motorized asset to its
    parent (bolted flanges, kinematic ball-groove couplings, V-rails,
    tapped-hole patterns). Functional naming covers mounts that are not
    strictly flanged."""


class UnitSystem(StrEnum):
    """The unit system a Placement's values are stored in.

    v1 ships with one value (`SI_MM_RAD`): translation in millimetres,
    rotation in radians. CORA stores canonically; conversion to or
    from facility-local units happens at the adapter boundary per
    `project_units_design.md` (canonical-stored, convert-at-edge).

    The single v1 value is what makes the design memo's
    "tolerance units MUST match value units per axis" invariant
    structurally satisfied: with one UnitSystem, a Placement's
    tolerances are by construction in the same units as its
    values. When a second UnitSystem lands (non-SI deployment),
    the per-axis coupling check must move from "trivially true" to
    an explicit `__post_init__` validation, OR Placement must widen
    to per-axis units fields. Capture this gate before widening
    the enum.
    """

    SI_MM_RAD = "SI_mm_rad"


@dataclass(frozen=True)
class Placement:
    """The pose (position + orientation) of a Mount or Frame.

    Flat 6 degrees of freedom: three translations (x, y, z) and
    three rotations (rx, ry, rz). Each value carries an independent
    `±` tolerance. All twelve numeric values are in the system named
    by `units` (v1: millimetres for translation, radians for rotation).

    `parent_frame_id` names the coordinate frame the values are measured
    against. `reference_surface` names the physical feature on the
    part the position is measured FROM.

    Equality and hash are structural across all 15 fields, so a
    Placement can live unambiguously in a frozenset.
    """

    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float
    parent_frame_id: UUID
    reference_surface: ReferenceSurface
    tol_x: float
    tol_y: float
    tol_z: float
    tol_rx: float
    tol_ry: float
    tol_rz: float
    units: UnitSystem

    def __post_init__(self) -> None:
        # Pure validation, no normalization (no trim or
        # `object.__setattr__` dance): all fields are typed
        # primitives or enums; only finiteness + tolerance non-negativity
        # are not encodable in the type itself.
        #
        # NaN/Inf rejection at the boundary: an unguarded NaN propagates
        # through the equality + comparison logic in update_mount_placement's
        # no-op-on-equal path (NaN != NaN, so every retry would re-emit
        # an event) and serializes as a JSON literal that asyncpg's
        # jsonb codec rejects at write time as a 500. Catch at the VO.
        for axis_name, value in (
            ("x", self.x),
            ("y", self.y),
            ("z", self.z),
            ("rx", self.rx),
            ("ry", self.ry),
            ("rz", self.rz),
            ("tol_x", self.tol_x),
            ("tol_y", self.tol_y),
            ("tol_z", self.tol_z),
            ("tol_rx", self.tol_rx),
            ("tol_ry", self.tol_ry),
            ("tol_rz", self.tol_rz),
        ):
            if not math.isfinite(value):
                raise InvalidPlacementError(f"{axis_name!s} must be finite (got: {value!r})")
        for tol_name, tol_value in (
            ("tol_x", self.tol_x),
            ("tol_y", self.tol_y),
            ("tol_z", self.tol_z),
            ("tol_rx", self.tol_rx),
            ("tol_ry", self.tol_ry),
            ("tol_rz", self.tol_rz),
        ):
            if tol_value < 0:
                raise InvalidPlacementError(
                    f"tolerance {tol_name!s} must be non-negative (got: {tol_value!r})"
                )


def placement_to_payload(placement: Placement) -> dict[str, object]:
    """Serialize a Placement VO to a JSON-friendly dict for jsonb storage.

    Canonical codec shared by every aggregate event that carries a
    Placement (Mount, Frame, Assembly). Sibling rebuilder is
    `placement_from_payload`. Hoisted to the VO module to close the
    duplication anti-hook flagged in `project_mount_frame_design`
    Watch items.
    """
    return {
        "x": placement.x,
        "y": placement.y,
        "z": placement.z,
        "rx": placement.rx,
        "ry": placement.ry,
        "rz": placement.rz,
        "parent_frame_id": str(placement.parent_frame_id),
        "reference_surface": placement.reference_surface.value,
        "tol_x": placement.tol_x,
        "tol_y": placement.tol_y,
        "tol_z": placement.tol_z,
        "tol_rx": placement.tol_rx,
        "tol_ry": placement.tol_ry,
        "tol_rz": placement.tol_rz,
        "units": placement.units.value,
    }


def placement_from_payload(payload: dict[str, object]) -> Placement:
    """Reconstruct a Placement VO from its JSON payload.

    Sibling of `placement_to_payload`. Round-trips losslessly with it.
    Re-runs Placement.__post_init__ validation so on-disk corruption
    (NaN, Inf, negative tolerance) surfaces at load time.
    """
    return Placement(
        x=payload["x"],  # type: ignore[arg-type]
        y=payload["y"],  # type: ignore[arg-type]
        z=payload["z"],  # type: ignore[arg-type]
        rx=payload["rx"],  # type: ignore[arg-type]
        ry=payload["ry"],  # type: ignore[arg-type]
        rz=payload["rz"],  # type: ignore[arg-type]
        parent_frame_id=UUID(str(payload["parent_frame_id"])),
        reference_surface=ReferenceSurface(str(payload["reference_surface"])),
        tol_x=payload["tol_x"],  # type: ignore[arg-type]
        tol_y=payload["tol_y"],  # type: ignore[arg-type]
        tol_z=payload["tol_z"],  # type: ignore[arg-type]
        tol_rx=payload["tol_rx"],  # type: ignore[arg-type]
        tol_ry=payload["tol_ry"],  # type: ignore[arg-type]
        tol_rz=payload["tol_rz"],  # type: ignore[arg-type]
        units=UnitSystem(str(payload["units"])),
    )


__all__ = [
    "Placement",
    "ReferenceSurface",
    "UnitSystem",
    "placement_from_payload",
    "placement_to_payload",
]

"""Seed Family registry: the closed-core device-class Families available at lifespan.

Companion to `_role_registry.SEED_ROLES`. Where `SEED_ROLES` seeds the
functional contracts, this seeds the anatomical device classes the
global fleet actually runs. The roster is the graduated set: every name
here is attested across at least three beamline descriptors under
`deployments/`, the same bar that produced `catalog/catalog.yaml`'s
`families:` list. The two stay in lockstep via
`test_families_match_seed_families`.

These constants do NOT register events at module import. Seeding is
performed via direct-append at lifespan-hook time (`bootstrap_families`),
mirroring `bootstrap_equipment` for Roles.

## Family id stability

Each Family id is `family_stream_id(name)` = `uuid5(namespace, NFC-lower
name)`, so the same device class resolves to the same id at every
facility. Federation-portability requires this: an `Assembly.content_hash`
serializes each slot's `required_family_ids`, so a `Camera` at APS 2-BM
and a `Camera` at MAX IV must share one id or the hash forks.

## Affordances and presents_as: authored per Role cluster

Affordances + `presents_as` are authored bottom-up in batches. Pass 1
(Role cluster) sets each family's affordances so it covers the Role it
presents (the `Family.affordances superset Role.required_affordances`
gate at `add_family_presents_as` / register_fixture), then wires
`presents_as`. Pass 2 (facility evidence) audits those drafts against the
deployment descriptors.

Every seed family now has a disposition (enforced by
`test_every_seed_family_reached_a_disposition`): it either presents a
Role, carries a functional affordance with no Role (an operable optic no
Method binds yet, e.g. Shutter -> Shutterable), or is explicitly empty (a
truly passive part like Window / Mask / BeamStop, or a provenance-only /
per-Asset-controlled family like InsertionDevice / Laser). A Role is
coined only when a Method binds it; the standalone affordance is the
forward seam for that future Role's required set.

The invariant that keeps this honest: a family's `affordances` MUST be a
superset of every presented Role's `required_affordances`. The
`test_seed_families_presents_as_affordance_cover` fitness test enforces it
so the seed can never ship a state the runtime gate would reject.
"""

from typing import Final

from cora.equipment.aggregates._value_types import RoleId
from cora.equipment.aggregates.family._family_registry import family_stream_id
from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.family.state import Family, FamilyName, FamilyStatus
from cora.equipment.aggregates.role._role_registry import (
    SEED_ROLE_CONTROLLER_ID,
    SEED_ROLE_DETECTOR_ID,
    SEED_ROLE_POSITIONER_ID,
    SEED_ROLE_REGULATOR_ID,
    SEED_ROLE_SENSOR_ID,
    SEED_ROLE_SHUTTER_ID,
)


def _family(
    name: str,
    *,
    affordances: frozenset[Affordance] = frozenset(),
    presents_as: frozenset[RoleId] = frozenset(),
) -> Family:
    """Build one seed Family: deterministic id, seeded affordances + presents_as."""
    family_name = FamilyName(name)
    return Family(
        id=family_stream_id(family_name),
        name=family_name,
        status=FamilyStatus.DEFINED,
        affordances=affordances,
        presents_as=presents_as,
    )


# Batch 1 (Pass 1, Positioner cluster). Each family's affordances cover
# Positioner's required_affordances {Homeable, Limitable}; the extra
# affordances are the top-down draft (audited against deployment
# descriptors in Pass 2). PseudoAxis is intentionally held out of this
# batch: it is a computed coordinate with no Homeable/Limitable hardware,
# so claiming those to satisfy the gate would model a lie; Pass 2 decides
# it from evidence.
_POSITIONER = frozenset({SEED_ROLE_POSITIONER_ID})
_DETECTOR = frozenset({SEED_ROLE_DETECTOR_ID})
_SENSOR = frozenset({SEED_ROLE_SENSOR_ID})
_REGULATOR = frozenset({SEED_ROLE_REGULATOR_ID})
_CONTROLLER = frozenset({SEED_ROLE_CONTROLLER_ID})
_SHUTTER = frozenset({SEED_ROLE_SHUTTER_ID})
_HOMED = frozenset({Affordance.HOMEABLE, Affordance.LIMITABLE})
_DETECTOR_AFFORDANCES = frozenset(
    {
        Affordance.IMAGEABLE,
        Affordance.BINNABLE,
        Affordance.COOLABLE,
        Affordance.TRIGGERABLE,
        Affordance.STREAMABLE,
        # Pass 2: fleet cameras (Eiger / Pilatus) write HDF5 / TIFF to disk
        # (iss, xfm, cdi), so the Camera Family records, not only streams.
        Affordance.RECORDING,
        # A camera's product IS a capture: the affordance's own contract
        # ("produces a Data BC Acquisition fact on every capture") is what
        # record_acquisition's Capturing gate checks, and the 2-BM pilot's
        # detector must pass it for ingest to record anything.
        Affordance.CAPTURING,
    }
)
# Batch 3 (Pass 1, Sensor cluster). Of the seven measurement/analyzer
# families, only the three point-measurement Sensors present the Sensor
# Role (scalar / short-vector Reading, not a 2D frame). The catalog notes
# assign the other four to Detector or Positioner INTENTIONALLY, so no
# Analyzer Role is coined here (deferred ANALYZER-1; it earns a lock only
# when a real Method needs an affordance set neither Detector nor Sensor
# covers). ElectronAnalyzer + EmissionSpectrometer acquire a spectrum ->
# Detector; PolarizationAnalyzer + SpectrometerArm are motorized arms ->
# Positioner.
_SENSOR_AFFORDANCES = frozenset(
    {Affordance.REPORTABLE, Affordance.TRIGGERABLE, Affordance.STREAMABLE}
)
# Pass 2 (facility evidence) narrowed the point-monitor Sensors to a bare
# scalar readout: ion chambers / picoammeters / quadrant monitors report a
# current or centroid on query, with no device-level trigger or stream
# hardware (chx/fmx/i03). Covers the Sensor required {Reportable}. The
# high-rate EnergyDispersiveSpectrometer (Xspress3 HDF5 streaming) keeps
# the fuller _SENSOR_AFFORDANCES set.
_SENSOR_SCALAR = frozenset({Affordance.REPORTABLE})
# Analyzer-detector families acquire a spectrum on a position-sensitive /
# area detector; Imageable + trigger/stream, but not the Camera's on-sensor
# Binnable/Coolable at the Family level (per-Asset bound-Model concern).
_ANALYZER_DETECTOR_AFFORDANCES = frozenset(
    {Affordance.IMAGEABLE, Affordance.TRIGGERABLE, Affordance.STREAMABLE}
)
# Batch 4 (Pass 1, Regulator cluster). All four sample-environment
# actuators drive a continuous process variable to a setpoint (Settable,
# the Regulator required affordance) and read it back (Reportable). The
# two that expose an operator-tunable control loop also carry
# PIDControllable; only TemperatureController exposes a cooling setpoint
# (Coolable). Field ramp (Magnet) and membrane/load pressure (PressureCell)
# are setpoint-driven but not operator-facing PID loops.
_REGULATOR_TEMPERATURE = frozenset(
    {
        Affordance.SETTABLE,
        Affordance.PID_CONTROLLABLE,
        Affordance.COOLABLE,
        Affordance.REPORTABLE,
    }
)
_REGULATOR_FLOW = frozenset(
    {Affordance.SETTABLE, Affordance.PID_CONTROLLABLE, Affordance.REPORTABLE}
)
_REGULATOR_SETPOINT = frozenset({Affordance.SETTABLE, Affordance.REPORTABLE})

# Batch 5 (Pass 1, Controller cluster). The two supervisory <Domain>Controller
# boxes present the Controller Role. They carry signal-governance affordances
# (Identifiable + status Reportable, plus Pulsing for the trigger generator),
# NOT the operational motion/imaging affordances of the subordinate Assets
# they govern. The Role's required {Identifiable} means a genuinely
# empty-affordance box cannot present it, so "empty-Affordances leaves" in the
# old docstring was reconciled to "signal-governance affordances" alongside
# this batch.
_CONTROLLER_MOTION = frozenset({Affordance.IDENTIFIABLE, Affordance.REPORTABLE})
_CONTROLLER_TIMING = frozenset({Affordance.IDENTIFIABLE, Affordance.PULSING, Affordance.REPORTABLE})

# Batch 2 (Pass 1, Detector cluster). Only direct-detection Camera
# presents the Detector Role; per the Role docstring a composed
# scintillator-relay Assembly is the OTHER path to Detector, so the bare
# Scintillator Family does NOT present it. Scintillator is a passive
# X-ray->light converter: its identity/material/thickness/lot are tracked
# (Consumable), no command surface, no Role. Screen also does not detect;
# its catalog note assigns it the Positioner Role for its insert axis, so
# it joins the Positioner cluster here.


# Batch 6 (Pass 1, passive / beam-conditioning tier). These families
# present NO Role: no Method binds them as a role_kind today. Per the
# locked principle, an affordance describes what a family CAN DO, but a
# Role is coined only when a Method binds it (the rule-of-three that
# graduated Regulator; the bar that deferred Conditioner). So operable
# optics carry their functional affordance as a forward seam -- when a
# Method later needs to bind e.g. an attenuator, `Attenuable` becomes that
# Role's required set and Filter already covers it. (Shutter has since
# crossed that trigger: three Methods bind a shutter, so it now presents
# the Shutter Role -- its Shutterable was exactly the seam. Attenuator /
# Bender remain affordance-only, un-earned.) Motorized != Positioner: a Slit
# is beam-defining, a Monochromator is energy-selecting; their driven axes
# are a per-Asset concern, not the Family's Role. Truly passive elements
# (Mask, Window, BeamStop, Collimator, Aperture) and provenance-only /
# per-Asset-controlled families (InsertionDevice, Backlight, Laser) stay
# empty. PhaseRetarder is the one exception: its catalog note assigns it
# the Positioner Role (the crystal angle IS its function, like
# PolarizationAnalyzer), so it joins that cluster.

# The graduated device-class roster. Order mirrors `catalog/catalog.yaml`
# `families:` for reviewer diffability. Adding a name here is a catalog
# graduation and must be matched in the catalog (drift-guard enforced).
SEED_FAMILIES: Final[tuple[Family, ...]] = (
    _family(
        "RotaryStage",
        affordances=_HOMED | {Affordance.ROTATABLE, Affordance.FOLLOWING, Affordance.MARKING},
        presents_as=_POSITIONER,
    ),
    _family(
        "LinearStage",
        affordances=_HOMED | {Affordance.TRANSLATABLE},
        presents_as=_POSITIONER,
    ),
    _family(
        "TiltStage",
        affordances=_HOMED | {Affordance.ROTATABLE},
        presents_as=_POSITIONER,
    ),
    _family(
        "Camera",
        affordances=_DETECTOR_AFFORDANCES,
        presents_as=_DETECTOR,
    ),
    _family("Scintillator", affordances=frozenset({Affordance.CONSUMABLE})),
    _family(
        "EnergyDispersiveSpectrometer",
        affordances=_SENSOR_AFFORDANCES,
        presents_as=_SENSOR,
    ),
    _family("FluxMonitor", affordances=_SENSOR_SCALAR, presents_as=_SENSOR),
    _family("PositionMonitor", affordances=_SENSOR_SCALAR, presents_as=_SENSOR),
    _family(
        "Shutter",
        affordances=frozenset({Affordance.SHUTTERABLE}),
        presents_as=_SHUTTER,
    ),
    _family(
        "Hexapod",
        affordances=_HOMED | {Affordance.POSABLE},
        presents_as=_POSITIONER,
    ),
    _family("MotionController", affordances=_CONTROLLER_MOTION, presents_as=_CONTROLLER),
    _family("TimingController", affordances=_CONTROLLER_TIMING, presents_as=_CONTROLLER),
    _family("Objective"),
    _family("PseudoAxis"),
    _family("Housing"),
    _family("GenericProbe"),
    _family(
        "Table",
        affordances=_HOMED | {Affordance.TRANSLATABLE},
        presents_as=_POSITIONER,
    ),
    _family("Slit", affordances=frozenset({Affordance.LIMITABLE})),
    _family("Aperture"),
    _family("Mask"),
    _family("Window"),
    _family("BeamStop"),
    _family("Collimator"),
    _family("Mirror", affordances=frozenset({Affordance.BENDABLE})),
    _family("Monochromator", affordances=frozenset({Affordance.INDEXABLE})),
    _family("GratingMonochromator", affordances=frozenset({Affordance.INDEXABLE})),
    _family("Condenser"),
    _family("ZonePlate"),
    _family("PhaseRing"),
    _family("Transfocator", affordances=frozenset({Affordance.INDEXABLE})),
    _family(
        "PhaseRetarder",
        affordances=_HOMED | {Affordance.ROTATABLE},
        presents_as=_POSITIONER,
    ),
    _family("Filter", affordances=frozenset({Affordance.ATTENUABLE})),
    _family("InsertionDevice"),
    _family(
        "Goniometer",
        # Pass 2: goniometers carry x/y/z sample-centring translations
        # alongside the orientation circles (Bernina GPS, 8-ID), so add
        # Translatable to the Rotatable draft.
        affordances=_HOMED | {Affordance.ROTATABLE, Affordance.TRANSLATABLE},
        presents_as=_POSITIONER,
    ),
    _family(
        "Manipulator",
        affordances=_HOMED | {Affordance.TRANSLATABLE, Affordance.ROTATABLE},
        presents_as=_POSITIONER,
    ),
    _family(
        "ElectronAnalyzer",
        affordances=_ANALYZER_DETECTOR_AFFORDANCES,
        presents_as=_DETECTOR,
    ),
    _family(
        "EmissionSpectrometer",
        affordances=_ANALYZER_DETECTOR_AFFORDANCES,
        presents_as=_DETECTOR,
    ),
    _family(
        "SpectrometerArm",
        affordances=_HOMED | {Affordance.TRANSLATABLE, Affordance.ROTATABLE},
        presents_as=_POSITIONER,
    ),
    _family(
        "TemperatureController",
        affordances=_REGULATOR_TEMPERATURE,
        presents_as=_REGULATOR,
    ),
    _family("FlowController", affordances=_REGULATOR_FLOW, presents_as=_REGULATOR),
    _family("Magnet", affordances=_REGULATOR_SETPOINT, presents_as=_REGULATOR),
    _family(
        "PolarizationAnalyzer",
        affordances=_HOMED | {Affordance.ROTATABLE},
        presents_as=_POSITIONER,
    ),
    _family("PressureCell", affordances=_REGULATOR_SETPOINT, presents_as=_REGULATOR),
    _family("Backlight"),
    _family("Laser"),
    _family(
        "Screen",
        affordances=_HOMED | {Affordance.TRANSLATABLE},
        presents_as=_POSITIONER,
    ),
)


__all__ = [
    "SEED_FAMILIES",
]

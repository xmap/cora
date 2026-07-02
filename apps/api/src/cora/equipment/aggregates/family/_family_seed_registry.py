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

## Affordances and presents_as: empty at seed, batched later

The seed ships every Family with `affordances=frozenset()` and
`presents_as=frozenset()`. The survey supplies the Family roster and its
frequency evidence, but carries no affordance or role data; those are a
CORA-lens modelling concern authored in later thematic batches (a Family
gains affordances via `version_family`, and presents Roles via
`add_family_presents_as`, both of which enforce the
`Family.affordances superset Role.required_affordances` gate). Until then
the affordance gates are intentionally dormant for seeded Families.
"""

from typing import Final

from cora.equipment.aggregates.family._family_registry import family_stream_id
from cora.equipment.aggregates.family.state import Family, FamilyName

# The graduated device-class roster. Order mirrors `catalog/catalog.yaml`
# `families:` for reviewer diffability. Adding a name here is a catalog
# graduation and must be matched in the catalog (drift-guard enforced).
_SEED_FAMILY_NAMES: Final[tuple[str, ...]] = (
    "RotaryStage",
    "LinearStage",
    "TiltStage",
    "Camera",
    "Scintillator",
    "EnergyDispersiveSpectrometer",
    "FluxMonitor",
    "PositionMonitor",
    "Shutter",
    "Hexapod",
    "MotionController",
    "TimingController",
    "Objective",
    "PseudoAxis",
    "Housing",
    "GenericProbe",
    "Table",
    "Slit",
    "Aperture",
    "Mask",
    "Window",
    "BeamStop",
    "Collimator",
    "Mirror",
    "Monochromator",
    "GratingMonochromator",
    "Condenser",
    "ZonePlate",
    "PhaseRing",
    "Transfocator",
    "PhaseRetarder",
    "Filter",
    "InsertionDevice",
    "Goniometer",
    "Manipulator",
    "ElectronAnalyzer",
    "EmissionSpectrometer",
    "SpectrometerArm",
    "TemperatureController",
    "FlowController",
    "Magnet",
    "PolarizationAnalyzer",
    "PressureCell",
    "Backlight",
    "Laser",
    "Screen",
)


def _seed_family(name: str) -> Family:
    """Build one seed Family: deterministic id, empty affordances + presents_as."""
    family_name = FamilyName(name)
    return Family(id=family_stream_id(family_name), name=family_name)


SEED_FAMILIES: Final[tuple[Family, ...]] = tuple(_seed_family(name) for name in _SEED_FAMILY_NAMES)


__all__ = [
    "SEED_FAMILIES",
]

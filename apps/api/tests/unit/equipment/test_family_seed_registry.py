"""Closed-set fitness for the Family seed registry.

The seed ships the graduated device-class roster (attested across at
least three beamline descriptors under `deployments/`, the same bar that
produced `catalog/catalog.yaml`'s `families:` list). Every change to the
seed list fires this test, keeping the closed-set claim enforceable and
in lockstep with the catalog (see test_catalog_descriptor).

Federation portability requires deterministic UUID5 ids: every
deployment computes the same Family id from the same name slug. This
test pins a representative sample so an accidental namespace edit
surfaces immediately.
"""

from uuid import UUID

import pytest

from cora.equipment.aggregates.family import SEED_FAMILIES, FamilyName, family_stream_id
from cora.equipment.aggregates.family.affordance import Affordance
from cora.equipment.aggregates.family.state import FamilyStatus
from cora.equipment.aggregates.role import SEED_ROLES

pytestmark = pytest.mark.unit


def test_seed_families_closed_set_count() -> None:
    """The graduated roster ships exactly 46 device-class Families."""
    assert len(SEED_FAMILIES) == 46


def test_seed_family_names_are_unique() -> None:
    names = [f.name.value for f in SEED_FAMILIES]
    assert len(names) == len(set(names))


def test_seed_family_names_include_anchor_classes() -> None:
    names = {f.name.value for f in SEED_FAMILIES}
    assert {"Camera", "RotaryStage", "LinearStage", "Slit", "Mirror"} <= names


def test_seed_family_ids_are_pairwise_distinct() -> None:
    ids = {f.id for f in SEED_FAMILIES}
    assert len(ids) == len(SEED_FAMILIES)


def test_seed_family_ids_are_deterministic_uuid5() -> None:
    """Federation-portable: id = uuid5(family namespace, NFC-lower name).

    Pins a representative sample; an accidental namespace or derivation
    edit surfaces here.
    """
    by_name = {f.name.value: f.id for f in SEED_FAMILIES}
    assert by_name["RotaryStage"] == UUID("ac85e2a5-19f3-579f-8111-f71d7822f539")
    assert by_name["Camera"] == UUID("28608285-97cb-57ec-a20d-09c33a0dba33")
    assert by_name["Slit"] == UUID("97de4203-605d-53e2-bb5f-a6f701e0b536")
    assert by_name["TemperatureController"] == UUID("901b0d23-ed39-5df2-87d3-548ea1ccf0b1")
    assert by_name["Backlight"] == UUID("8c31653b-45c8-5ea6-86ea-acd5bd7d5658")


def test_seed_family_ids_match_family_stream_id() -> None:
    """Every seed id is exactly family_stream_id(name) (no drift)."""
    for family in SEED_FAMILIES:
        assert family.id == family_stream_id(FamilyName(family.name.value))


def test_seed_families_ship_defined_status() -> None:
    for family in SEED_FAMILIES:
        assert family.status is FamilyStatus.DEFINED


def test_seed_family_presents_as_is_covered_by_affordances() -> None:
    """A seed Family may present a Role only when its own affordances cover
    that Role's required_affordances. This is the exact invariant the
    add_family_presents_as decider and the register_fixture union check
    enforce at runtime, so the seed can never ship a state the gate would
    reject."""
    required_by_role_id = {role.id: role.required_affordances for role in SEED_ROLES}
    for family in SEED_FAMILIES:
        for role_id in family.presents_as:
            required = required_by_role_id[role_id]
            missing = required - family.affordances
            assert missing == frozenset(), (
                f"Seed Family {family.name.value} presents Role {role_id} but its "
                f"affordances miss {sorted(a.value for a in missing)}"
            )


def test_seed_family_presents_as_only_references_seed_roles() -> None:
    """Every presented Role id resolves to a seeded Role (no dangling id)."""
    seed_role_ids = {role.id for role in SEED_ROLES}
    for family in SEED_FAMILIES:
        assert family.presents_as <= seed_role_ids, (
            f"Seed Family {family.name.value} presents a non-seed Role id"
        )


def test_positioner_cluster_is_populated() -> None:
    """The families presenting Positioner; guards against an accidental
    drop when later batches edit the registry. Screen joins via its insert
    axis (Batch 2 evidence: it is a viewing target, not a detector)."""
    positioner_id = next(r.id for r in SEED_ROLES if r.name.value == "Positioner")
    presenting = {f.name.value for f in SEED_FAMILIES if positioner_id in f.presents_as}
    assert presenting == {
        "RotaryStage",
        "LinearStage",
        "TiltStage",
        "Hexapod",
        "Table",
        "Goniometer",
        "Manipulator",
        "Screen",
        # Batch 3: motorized analyzer arms (measure by positioning, not by
        # detecting a scalar), per their catalog notes.
        "SpectrometerArm",
        "PolarizationAnalyzer",
    }


def test_detector_cluster_is_populated() -> None:
    """The families presenting Detector. Direct-detection Camera plus the
    two analyzer-detectors that acquire a spectrum on an area /
    position-sensitive detector (ElectronAnalyzer, EmissionSpectrometer),
    per their catalog notes. Scintillator is a Consumable component of a
    composed detector Assembly (the Assembly presents the Role, not the
    bare Family), so it must NOT present Detector."""
    detector_id = next(r.id for r in SEED_ROLES if r.name.value == "Detector")
    presenting = {f.name.value for f in SEED_FAMILIES if detector_id in f.presents_as}
    assert presenting == {"Camera", "ElectronAnalyzer", "EmissionSpectrometer"}

    scintillator = next(f for f in SEED_FAMILIES if f.name.value == "Scintillator")
    assert scintillator.presents_as == frozenset()
    assert scintillator.affordances == frozenset({Affordance.CONSUMABLE})


def test_regulator_cluster_is_populated() -> None:
    """Batch 4 (Regulator cluster): the four sample-environment actuators
    that drive a process variable to a setpoint. Each carries Settable
    (the Regulator required affordance)."""
    regulator_id = next(r.id for r in SEED_ROLES if r.name.value == "Regulator")
    presenting = {f.name.value for f in SEED_FAMILIES if regulator_id in f.presents_as}
    assert presenting == {
        "TemperatureController",
        "FlowController",
        "Magnet",
        "PressureCell",
    }
    for family in SEED_FAMILIES:
        if regulator_id in family.presents_as:
            assert Affordance.SETTABLE in family.affordances


def test_sensor_cluster_is_populated() -> None:
    """Batch 3 (Sensor cluster): only the three point-measurement Sensors
    present the Sensor Role (scalar / short-vector Reading). No Analyzer
    Role is coined; the analyzer families claim Detector/Positioner
    intentionally per their catalog notes (deferred ANALYZER-1)."""
    sensor_id = next(r.id for r in SEED_ROLES if r.name.value == "Sensor")
    presenting = {f.name.value for f in SEED_FAMILIES if sensor_id in f.presents_as}
    assert presenting == {
        "EnergyDispersiveSpectrometer",
        "FluxMonitor",
        "PositionMonitor",
    }

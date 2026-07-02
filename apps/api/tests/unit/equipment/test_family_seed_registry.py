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
from cora.equipment.aggregates.family.state import FamilyStatus

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


def test_seed_families_ship_empty_affordances_and_presents_as() -> None:
    """Affordances + presents_as are authored in later thematic batches;
    the seed ships them empty (see the registry module docstring)."""
    for family in SEED_FAMILIES:
        assert family.affordances == frozenset(), (
            f"Seed Family {family.name.value} ships non-empty affordances; "
            "affordances are populated in a later batch, alongside the catalog"
        )
        assert family.presents_as == frozenset()

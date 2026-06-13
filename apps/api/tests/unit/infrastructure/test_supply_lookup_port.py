"""Unit tests for the `SupplyLookup` port value types and test stubs.

Pins the `SupplyLookupResult` dataclass contract that cross-BC
consumers rely on plus the `find_supplies_by_name` test-default
behavior across all four in-source stubs. The by-name path is wired
to the real `PostgresSupplyLookup` adapter by the Data BC lifespan
bootstrap (covered by `test_distribution_backfill_bootstrap` and
`test_postgres_supply_lookup`); these stubs exist so tests not
exercising that path get an empty result without seeding projection
rows. The inline-stub shape mirrors `test_enclosure_lookup_port`.
"""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from cora.infrastructure.ports import (
    AllSatisfiedSupplyLookup,
    SupplyLookup,
    SupplyLookupResult,
)
from cora.infrastructure.ports.supply_lookup import (
    NoSuppliesRegisteredLookup,
    SingleSupplyLookup,
    UnknownSupplyLookup,
)
from cora.infrastructure.ports.supply_lookup import (
    SupplyLookup as SupplyLookupFromModule,
)
from cora.infrastructure.ports.supply_lookup import (
    SupplyLookupResult as SupplyLookupResultFromModule,
)


def _reference() -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=uuid4(),
        kind="Storage",
        name="primary-store",
        status="Available",
        facility_code="cora",
    )


@pytest.mark.unit
def test_supply_lookup_result_carries_all_five_fields() -> None:
    sid = uuid4()
    ref = SupplyLookupResult(
        supply_id=sid,
        kind="Storage",
        name="primary-store",
        status="Available",
        facility_code="cora",
    )
    assert ref.supply_id == sid
    assert ref.kind == "Storage"
    assert ref.name == "primary-store"
    assert ref.status == "Available"
    assert ref.facility_code == "cora"


@pytest.mark.unit
def test_supply_lookup_result_is_frozen() -> None:
    ref = _reference()
    with pytest.raises(FrozenInstanceError):
        ref.status = "Unavailable"  # type: ignore[misc]


@pytest.mark.unit
async def test_all_satisfied_supply_lookup_find_supplies_by_name_returns_empty_list() -> None:
    """The default stub does not back the by-name path; tests exercising
    it wire the real `PostgresSupplyLookup` adapter instead."""
    lookup: SupplyLookup = AllSatisfiedSupplyLookup()
    result = await lookup.find_supplies_by_name(
        name="primary-store", facility_code="cora", kind="Storage"
    )
    assert result == []


@pytest.mark.unit
async def test_no_supplies_registered_lookup_find_supplies_by_name_returns_empty_list() -> None:
    lookup: SupplyLookup = NoSuppliesRegisteredLookup()
    result = await lookup.find_supplies_by_name(
        name="primary-store", facility_code="cora", kind="Storage"
    )
    assert result == []


@pytest.mark.unit
async def test_unknown_supply_lookup_find_supplies_by_name_returns_empty_list() -> None:
    lookup: SupplyLookup = UnknownSupplyLookup()
    result = await lookup.find_supplies_by_name(
        name="primary-store", facility_code="cora", kind="Storage"
    )
    assert result == []


@pytest.mark.unit
async def test_single_supply_lookup_find_supplies_by_name_returns_empty_list() -> None:
    """`SingleSupplyLookup` backs only the single-id `lookup`; the by-name
    path is out of scope and returns empty regardless of its reference."""
    lookup: SupplyLookup = SingleSupplyLookup(_reference())
    result = await lookup.find_supplies_by_name(
        name="primary-store", facility_code="cora", kind="Storage"
    )
    assert result == []


@pytest.mark.unit
def test_supply_lookup_names_re_exported_from_ports_package() -> None:
    assert SupplyLookup is SupplyLookupFromModule
    assert SupplyLookupResult is SupplyLookupResultFromModule

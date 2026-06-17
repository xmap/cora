"""Unit tests for `InMemoryEnclosureLookup` (the test-tier adapter).

Mirrors the production `PostgresEnclosureLookup` contract under
the in-memory adapter:
  - `register()` installs an enclosure summary keyed by id.
  - `lookup()` returns the seeded `EnclosureLookupResult`.
  - `lookup()` returns `None` for an unknown id.
  - `find_by_ids()` returns every reference whose `enclosure_id` is in
    the requested set, excluding Decommissioned (per the production
    adapter's `lifecycle = 'Active'` partial-index posture).
  - The ctor-side `seed=` mapping is an alternative bulk-seed path.
  - The adapter satisfies the `EnclosureLookup` Protocol shape.

Separate from the inline `AlwaysPermittedEnclosureLookup` stub in
`cora.infrastructure.ports.enclosure_lookup`: the stub is the
test-default behavioural shortcut; this adapter is the seedable
test surface for handler tests that need specific rows.
"""

from uuid import uuid4

import pytest

from cora.infrastructure.adapters.in_memory_enclosure_lookup import (
    InMemoryEnclosureLookup,
)
from cora.infrastructure.ports import (
    EnclosureLookup,
    EnclosureLookupResult,
)


@pytest.mark.unit
async def test_register_then_lookup_returns_seeded_result() -> None:
    lookup = InMemoryEnclosureLookup()
    eid = uuid4()
    lookup.register(
        enclosure_id=eid,
        name="2-BM-A Hutch",
        permit_status="Permitted",
        lifecycle="Active",
        observed_at="2026-06-09T12:00:00+00:00",
        source_kind="EpicsPv",
        source_id="2bma:hutch:permit",
    )
    result = await lookup.lookup(eid)
    assert result is not None
    assert result.enclosure_id == eid
    assert result.name == "2-BM-A Hutch"
    assert result.permit_status == "Permitted"
    assert result.lifecycle == "Active"
    assert result.observed_at == "2026-06-09T12:00:00+00:00"
    assert result.source_kind == "EpicsPv"
    assert result.source_id == "2bma:hutch:permit"


@pytest.mark.unit
async def test_lookup_unknown_id_returns_none() -> None:
    lookup = InMemoryEnclosureLookup()
    lookup.register(enclosure_id=uuid4(), name="2-BM-A Hutch")
    assert await lookup.lookup(uuid4()) is None


@pytest.mark.unit
async def test_lookup_on_empty_adapter_returns_none() -> None:
    lookup = InMemoryEnclosureLookup()
    assert await lookup.lookup(uuid4()) is None


@pytest.mark.unit
async def test_register_overwrites_existing_record() -> None:
    lookup = InMemoryEnclosureLookup()
    eid = uuid4()
    lookup.register(enclosure_id=eid, name="2-BM-A Hutch", permit_status="Unknown")
    lookup.register(
        enclosure_id=eid,
        name="2-BM-A Hutch",
        permit_status="Permitted",
        observed_at="2026-06-09T12:30:00+00:00",
    )
    result = await lookup.lookup(eid)
    assert result is not None
    assert result.permit_status == "Permitted"
    assert result.observed_at == "2026-06-09T12:30:00+00:00"


@pytest.mark.unit
async def test_ctor_seed_mapping_populates_records() -> None:
    eid_a, eid_b = uuid4(), uuid4()
    seed = {
        eid_a: EnclosureLookupResult(
            enclosure_id=eid_a,
            name="A",
            permit_status="Permitted",
            lifecycle="Active",
            observed_at=None,
            source_kind=None,
            source_id=None,
        ),
        eid_b: EnclosureLookupResult(
            enclosure_id=eid_b,
            name="B",
            permit_status="NotPermitted",
            lifecycle="Active",
            observed_at=None,
            source_kind=None,
            source_id=None,
        ),
    }
    lookup = InMemoryEnclosureLookup(seed=seed)
    a = await lookup.lookup(eid_a)
    b = await lookup.lookup(eid_b)
    assert a is not None and a.name == "A"
    assert b is not None and b.name == "B"


@pytest.mark.unit
async def test_returns_enclosures_in_every_permit_status() -> None:
    lookup = InMemoryEnclosureLookup()
    np = uuid4()
    uk = uuid4()
    lookup.register(enclosure_id=np, name="A", permit_status="NotPermitted")
    lookup.register(enclosure_id=uk, name="B", permit_status="Unknown")
    nq = await lookup.lookup(np)
    uq = await lookup.lookup(uk)
    assert nq is not None and nq.permit_status == "NotPermitted"
    assert uq is not None and uq.permit_status == "Unknown"


@pytest.mark.unit
async def test_find_by_ids_returns_matching_enclosures() -> None:
    lookup = InMemoryEnclosureLookup()
    eid_a, eid_b = uuid4(), uuid4()
    lookup.register(enclosure_id=eid_a, name="A", permit_status="Permitted")
    lookup.register(enclosure_id=eid_b, name="B", permit_status="NotPermitted")
    results = await lookup.find_by_ids(enclosure_ids=frozenset({eid_a}))
    assert len(results) == 1
    assert results[0].enclosure_id == eid_a
    assert results[0].permit_status == "Permitted"


@pytest.mark.unit
async def test_find_by_ids_skips_non_matching_ids() -> None:
    lookup = InMemoryEnclosureLookup()
    lookup.register(enclosure_id=uuid4(), name="A", permit_status="Permitted")
    assert await lookup.find_by_ids(enclosure_ids=frozenset({uuid4()})) == []


@pytest.mark.unit
async def test_find_by_ids_empty_input_returns_empty_list() -> None:
    lookup = InMemoryEnclosureLookup()
    lookup.register(enclosure_id=uuid4(), name="A", permit_status="Permitted")
    assert await lookup.find_by_ids(enclosure_ids=frozenset()) == []


@pytest.mark.unit
async def test_find_by_ids_returns_multiple_for_a_set() -> None:
    lookup = InMemoryEnclosureLookup()
    eid_a, eid_b = uuid4(), uuid4()
    lookup.register(enclosure_id=eid_a, name="A", permit_status="Permitted")
    lookup.register(enclosure_id=eid_b, name="B", permit_status="Unknown")
    results = await lookup.find_by_ids(enclosure_ids=frozenset({eid_a, eid_b}))
    returned = {r.enclosure_id for r in results}
    assert returned == {eid_a, eid_b}


@pytest.mark.unit
async def test_find_by_ids_excludes_decommissioned() -> None:
    """Tombstoned rows must not gate runs; matches PostgresEnclosureLookup
    `lifecycle = 'Active'` partial-index filter."""
    lookup = InMemoryEnclosureLookup()
    eid_active = uuid4()
    eid_tomb = uuid4()
    lookup.register(
        enclosure_id=eid_active,
        name="live",
        permit_status="Permitted",
        lifecycle="Active",
    )
    lookup.register(
        enclosure_id=eid_tomb,
        name="dead",
        permit_status="Permitted",
        lifecycle="Decommissioned",
    )
    results = await lookup.find_by_ids(enclosure_ids=frozenset({eid_active, eid_tomb}))
    returned = {r.enclosure_id for r in results}
    assert eid_active in returned
    assert eid_tomb not in returned


@pytest.mark.unit
async def test_lookup_by_name_resolves_active_address() -> None:
    lookup = InMemoryEnclosureLookup()
    eid = uuid4()
    lookup.register(enclosure_id=eid, name="2-BM-A", facility_code="aps", permit_status="Permitted")
    result = await lookup.lookup_by_name(facility_code="aps", name="2-BM-A")
    assert result is not None
    assert result.enclosure_id == eid


@pytest.mark.unit
async def test_lookup_by_name_resolves_to_active_when_address_reused() -> None:
    """Decommission + re-register at the same (facility, name) address keeps
    a tombstoned row and a fresh Active one; lookup_by_name returns the
    Active one (the live enclosure operators currently mean)."""
    lookup = InMemoryEnclosureLookup()
    tomb, live = uuid4(), uuid4()
    lookup.register(
        enclosure_id=tomb, name="2-BM-A", facility_code="aps", lifecycle="Decommissioned"
    )
    lookup.register(enclosure_id=live, name="2-BM-A", facility_code="aps", lifecycle="Active")
    result = await lookup.lookup_by_name(facility_code="aps", name="2-BM-A")
    assert result is not None
    assert result.enclosure_id == live


@pytest.mark.unit
async def test_lookup_by_name_distinguishes_facility() -> None:
    lookup = InMemoryEnclosureLookup()
    lookup.register(enclosure_id=uuid4(), name="2-BM-A", facility_code="aps")
    assert await lookup.lookup_by_name(facility_code="max-iv", name="2-BM-A") is None


@pytest.mark.unit
async def test_lookup_by_name_unknown_address_returns_none() -> None:
    lookup = InMemoryEnclosureLookup()
    lookup.register(enclosure_id=uuid4(), name="2-BM-A", facility_code="aps")
    assert await lookup.lookup_by_name(facility_code="aps", name="2-BM-B") is None


@pytest.mark.unit
def test_satisfies_enclosure_lookup_protocol() -> None:
    lookup: EnclosureLookup = InMemoryEnclosureLookup()
    assert lookup is not None

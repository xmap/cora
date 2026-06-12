"""Unit tests for `InMemoryClearanceTemplateLookup` (the test-tier adapter).

Mirrors the production `PostgresClearanceTemplateLookup` contract under
the in-memory adapter:
  - `lookup()` returns `None` for an unknown id (None-on-missing
    semantics; deciders translate to domain errors).
  - `register()` installs a clearance-template summary keyed by id.
  - `register()` defaults to facility `aps`, status `Active`, version 1
    (the steady state for a freshly-activated template ready to be
    superseded by a new version).
  - The ctor-side `seed=` mapping is an alternative bulk-seed path.
  - Two distinct ids are stored as independent records.
"""

from uuid import uuid4

import pytest

from cora.infrastructure.adapters.in_memory_clearance_template_lookup import (
    InMemoryClearanceTemplateLookup,
)
from cora.infrastructure.ports.clearance_template_lookup import (
    ClearanceTemplateLookupResult,
)


@pytest.mark.unit
async def test_lookup_by_id_returns_none_when_unseeded() -> None:
    lookup = InMemoryClearanceTemplateLookup()
    assert await lookup.lookup(uuid4()) is None


@pytest.mark.unit
async def test_register_then_lookup_by_id_returns_seeded_result() -> None:
    lookup = InMemoryClearanceTemplateLookup()
    tid = uuid4()
    lookup.register(
        template_id=tid,
        facility_code="aps-2bm",
        code="radiation-safety",
        status="Active",
        version=3,
    )

    result = await lookup.lookup(tid)
    assert result is not None
    assert result.id == tid
    assert result.facility_code == "aps-2bm"
    assert result.code == "radiation-safety"
    assert result.status == "Active"
    assert result.version == 3


@pytest.mark.unit
async def test_register_defaults_facility_code_to_aps_and_status_to_active() -> None:
    lookup = InMemoryClearanceTemplateLookup()
    tid = uuid4()
    lookup.register(template_id=tid)

    result = await lookup.lookup(tid)
    assert result is not None
    assert result.facility_code == "aps"
    assert result.status == "Active"
    assert result.version == 1
    assert result.code == "default-template"


@pytest.mark.unit
async def test_seed_constructor_pre_populates_dict_and_lookup_returns_seeded_result() -> None:
    tid = uuid4()
    seed = {
        tid: ClearanceTemplateLookupResult(
            id=tid,
            facility_code="aps-2bm",
            code="laser-safety",
            status="Active",
            version=2,
        ),
    }
    lookup = InMemoryClearanceTemplateLookup(seed=seed)

    result = await lookup.lookup(tid)
    assert result is not None
    assert result.id == tid
    assert result.code == "laser-safety"
    assert result.version == 2


@pytest.mark.unit
async def test_lookup_by_id_distinguishes_two_seeded_ids() -> None:
    lookup = InMemoryClearanceTemplateLookup()
    tid_a = uuid4()
    tid_b = uuid4()
    lookup.register(template_id=tid_a, code="radiation-safety", version=1)
    lookup.register(template_id=tid_b, code="laser-safety", version=4)

    result_a = await lookup.lookup(tid_a)
    result_b = await lookup.lookup(tid_b)
    assert result_a is not None
    assert result_a.id == tid_a
    assert result_a.code == "radiation-safety"
    assert result_a.version == 1
    assert result_b is not None
    assert result_b.id == tid_b
    assert result_b.code == "laser-safety"
    assert result_b.version == 4

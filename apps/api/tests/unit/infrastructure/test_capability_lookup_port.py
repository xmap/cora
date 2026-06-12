"""Unit tests for the `CapabilityLookup` port value types.

Pins the `CapabilityLookupResult` dataclass contract that Equipment's
`get_asset_integration_view` handler relies on, plus the
`AlwaysEmptyCapabilityLookup` test-default returning `[]`.
"""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from cora.infrastructure.ports import (
    AlwaysEmptyCapabilityLookup,
    CapabilityLookup,
    CapabilityLookupResult,
)


@pytest.mark.unit
def test_capability_reference_carries_all_four_fields() -> None:
    cid = uuid4()
    ref = CapabilityLookupResult(
        capability_id=cid,
        code="cora.capability.tomo",
        name="TomoScan",
        status="Defined",
    )
    assert ref.capability_id == cid
    assert ref.code == "cora.capability.tomo"
    assert ref.name == "TomoScan"
    assert ref.status == "Defined"


@pytest.mark.unit
def test_capability_reference_is_frozen() -> None:
    ref = CapabilityLookupResult(
        capability_id=uuid4(),
        code="cora.capability.tomo",
        name="TomoScan",
        status="Defined",
    )
    with pytest.raises(FrozenInstanceError):
        ref.status = "Deprecated"  # type: ignore[misc]


@pytest.mark.unit
def test_capability_reference_supports_value_equality() -> None:
    cid = uuid4()
    a = CapabilityLookupResult(capability_id=cid, code="x", name="X", status="Defined")
    b = CapabilityLookupResult(capability_id=cid, code="x", name="X", status="Defined")
    assert a == b


@pytest.mark.unit
async def test_always_empty_capability_lookup_returns_empty_list() -> None:
    """Test-default stub: every call returns []. Affordance set is ignored;
    the stub exists so tests not exercising the surface do not need to
    seed Capability projection rows."""
    lookup: CapabilityLookup = AlwaysEmptyCapabilityLookup()
    result_empty = await lookup.find_applicable_by_affordances(frozenset())
    assert result_empty == []
    result_populated = await lookup.find_applicable_by_affordances(
        frozenset({"Rotatable", "Triggerable"})
    )
    assert result_populated == []

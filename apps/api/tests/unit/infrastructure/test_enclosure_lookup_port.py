"""Unit tests for the `EnclosureLookup` port value types.

Pins the `EnclosureReference` dataclass contract that cross-BC
consumers rely on plus the `AlwaysPermittedEnclosureLookup` test-
default returning a synthetic Active+Permitted row from `lookup(...)`
and `[]` from `find_for_assets(...)`. The stub exists so tests not
exercising the Enclosure surface do not need to seed projection
rows; the inline-stub shape mirrors `AlwaysEmptyCapabilityLookup` /
`AlwaysQuietCautionLookup` / `AllSatisfiedSupplyLookup`. All
`EnclosureReference` fields stay as bare `str` / bare `UUID` so
`cora.infrastructure.ports` stays free of Enclosure BC enum imports
per the kernel-tier dependency discipline.
"""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from cora.infrastructure.ports import (
    AlwaysPermittedEnclosureLookup,
    EnclosureLookup,
    EnclosureReference,
)
from cora.infrastructure.ports.enclosure_lookup import (
    AlwaysPermittedEnclosureLookup as AlwaysPermittedEnclosureLookupFromModule,
)
from cora.infrastructure.ports.enclosure_lookup import (
    EnclosureLookup as EnclosureLookupFromModule,
)
from cora.infrastructure.ports.enclosure_lookup import (
    EnclosureReference as EnclosureReferenceFromModule,
)


@pytest.mark.unit
def test_enclosure_reference_carries_all_eight_fields() -> None:
    eid = uuid4()
    aid = uuid4()
    ref = EnclosureReference(
        enclosure_id=eid,
        name="Station A Hutch",
        containing_asset_id=aid,
        permit_status="Permitted",
        lifecycle="Active",
        observed_at="2026-06-09T12:00:00Z",
        source_kind="EpicsPv",
        source_id="2bma:hutch:permitted",
    )
    assert ref.enclosure_id == eid
    assert ref.name == "Station A Hutch"
    assert ref.containing_asset_id == aid
    assert ref.permit_status == "Permitted"
    assert ref.lifecycle == "Active"
    assert ref.observed_at == "2026-06-09T12:00:00Z"
    assert ref.source_kind == "EpicsPv"
    assert ref.source_id == "2bma:hutch:permitted"


@pytest.mark.unit
def test_enclosure_reference_allows_optional_observation_fields_to_be_none() -> None:
    ref = EnclosureReference(
        enclosure_id=uuid4(),
        name="Station A Hutch",
        containing_asset_id=uuid4(),
        permit_status="Unknown",
        lifecycle="Active",
        observed_at=None,
        source_kind=None,
        source_id=None,
    )
    assert ref.observed_at is None
    assert ref.source_kind is None
    assert ref.source_id is None


@pytest.mark.unit
def test_enclosure_reference_is_frozen() -> None:
    ref = EnclosureReference(
        enclosure_id=uuid4(),
        name="Station A Hutch",
        containing_asset_id=uuid4(),
        permit_status="Permitted",
        lifecycle="Active",
        observed_at=None,
        source_kind=None,
        source_id=None,
    )
    with pytest.raises(FrozenInstanceError):
        ref.permit_status = "NotPermitted"  # type: ignore[misc]


@pytest.mark.unit
def test_enclosure_reference_status_and_lifecycle_are_str() -> None:
    """Port keeps `permit_status` and `lifecycle` as plain `str` so
    callers compare via literals (`== "Permitted"`, `== "Active"`)
    and the port stays free of Enclosure BC enum imports."""
    ref = EnclosureReference(
        enclosure_id=uuid4(),
        name="Station A Hutch",
        containing_asset_id=uuid4(),
        permit_status="Permitted",
        lifecycle="Active",
        observed_at=None,
        source_kind=None,
        source_id=None,
    )
    assert isinstance(ref.permit_status, str)
    assert isinstance(ref.lifecycle, str)


@pytest.mark.unit
async def test_always_permitted_enclosure_lookup_returns_active_permitted_reference() -> None:
    """Test-default stub: `lookup(enclosure_id)` synthesizes an
    Active+Permitted row for any UUID."""
    lookup: EnclosureLookup = AlwaysPermittedEnclosureLookup()
    eid = uuid4()
    result = await lookup.lookup(eid)
    assert result is not None
    assert result.enclosure_id == eid
    assert result.permit_status == "Permitted"
    assert result.lifecycle == "Active"


@pytest.mark.unit
async def test_always_permitted_enclosure_lookup_echoes_distinct_ids() -> None:
    lookup: EnclosureLookup = AlwaysPermittedEnclosureLookup()
    a, b = uuid4(), uuid4()
    result_a = await lookup.lookup(a)
    result_b = await lookup.lookup(b)
    assert result_a is not None and result_a.enclosure_id == a
    assert result_b is not None and result_b.enclosure_id == b


@pytest.mark.unit
async def test_always_permitted_enclosure_lookup_find_for_assets_returns_empty_list() -> None:
    lookup: EnclosureLookup = AlwaysPermittedEnclosureLookup()
    assert await lookup.find_for_assets(asset_ids=frozenset()) == []
    assert await lookup.find_for_assets(asset_ids=frozenset({uuid4(), uuid4()})) == []


@pytest.mark.unit
def test_always_permitted_enclosure_lookup_satisfies_enclosure_lookup_protocol() -> None:
    """Structural conformance via typed assignment; `EnclosureLookup`
    is not `runtime_checkable`."""
    lookup: EnclosureLookup = AlwaysPermittedEnclosureLookup()
    assert lookup is not None


@pytest.mark.unit
def test_enclosure_lookup_names_re_exported_from_ports_package() -> None:
    assert EnclosureLookup is EnclosureLookupFromModule
    assert EnclosureReference is EnclosureReferenceFromModule
    assert AlwaysPermittedEnclosureLookup is AlwaysPermittedEnclosureLookupFromModule

"""Unit tests for the `get_fixture` query handler.

Mirrors test_get_family_handler.py / test_get_asset_handler.py.
Round-trips through the write side (register_fixture -> get_fixture)
verify that fold-on-read correctly returns the registered Fixture.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.fixture import Fixture, SlotAssetBinding
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features import (
    add_asset_family,
    define_assembly,
    define_family,
    get_fixture,
    register_asset,
    register_fixture,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.get_fixture import GetFixture
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_fixture import RegisterFixture
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import Authorize
from tests.unit._helpers import DenyAllAuthorize as _DenyAllAuthorize
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 4, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(*, authz: Authorize | None = None) -> Kernel:
    return _build_deps_shared(
        ids=[UUID(f"01900000-0000-7000-8000-00000054fb{i:02x}") for i in range(20)],
        now=_NOW,
        authz=authz,
    )


async def _seed_fixture(deps: Kernel) -> UUID:
    family_id = await define_family.bind(deps)(
        DefineFamily(name="Camera", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="Cam-1", tier=AssetTier.DEVICE, parent_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(
            name="Microscope",
            presents_as=frozenset(),
            required_slots=frozenset(
                {
                    TemplateSlot(
                        slot_name=SlotName("camera"),
                        required_family_ids=frozenset({family_id}),
                        cardinality=SlotCardinality.EXACTLY_1,
                    )
                }
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    fixture_id = await register_fixture.bind(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return fixture_id


@pytest.mark.unit
async def test_handler_returns_fixture_for_known_id() -> None:
    """Round-trip: register + get."""
    deps = _build_deps()
    fixture_id = await _seed_fixture(deps)
    fixture = await get_fixture.bind(deps)(
        GetFixture(fixture_id=fixture_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert fixture is not None
    assert isinstance(fixture, Fixture)
    assert fixture.id == fixture_id
    assert len(fixture.slot_asset_bindings) == 1


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = _build_deps()
    fixture = await get_fixture.bind(deps)(
        GetFixture(fixture_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert fixture is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_when_authz_denies() -> None:
    deps = _build_deps(authz=_DenyAllAuthorize())
    with pytest.raises(UnauthorizedError):
        await get_fixture.bind(deps)(
            GetFixture(fixture_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

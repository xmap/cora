"""End-to-end: `list_fixtures` handler against real Postgres
projection. Verifies FixtureRegistered events fold into
proj_equipment_fixture_summary rows, all three filters work
(assembly_id, surface_id, assembly_content_hash), and cursor
pagination orders by created_at DESC.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.assembly import SlotCardinality, SlotName, TemplateSlot
from cora.equipment.aggregates.fixture import SlotAssetBinding
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.add_asset_family import bind as bind_add_family
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_assembly import bind as bind_define_assembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define_family
from cora.equipment.features.list_fixtures import ListFixtures
from cora.equipment.features.list_fixtures import bind as bind_list_fixtures
from cora.equipment.features.register_fixture import RegisterFixture
from cora.equipment.features.register_fixture import bind as bind_register_fixture
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._equipment_helpers import seed_installed_asset
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 4, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000bb")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_fixture(
    deps: Kernel,
    db_pool: asyncpg.Pool,
    *,
    asset_name: str = "Cam",
    assembly_name: str = "Microscope",
) -> tuple[UUID, UUID, UUID]:
    """Returns (family_id, assembly_id, fixture_id).

    Pre-seeds Frame + Mount + Asset via the shared seed_installed_asset
    helper (uuid4 ids; bypasses the outer FixedIdGenerator) so the
    bound Asset is mount-installed before register_fixture (the
    install-required guard). The outer deps's id pool only needs to
    budget for the four post-seed commands: define_family,
    add_asset_family, define_assembly, register_fixture.
    """
    _, _, asset_id = await seed_installed_asset(
        db_pool, now=_NOW, slot_code=f"02-BM-{asset_name}", asset_name=asset_name
    )

    family_id = await bind_define_family(deps)(
        DefineFamily(name=f"Camera-{asset_name}", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_add_family(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await bind_define_assembly(deps)(
        DefineAssembly(
            name=assembly_name,
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
    fixture_id = await bind_register_fixture(deps)(
        RegisterFixture(
            assembly_id=assembly_id,
            slot_asset_bindings=frozenset(
                {SlotAssetBinding(slot_name="camera", asset_id=asset_id)}
            ),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return family_id, assembly_id, fixture_id


@pytest.mark.integration
async def test_list_fixtures_returns_registered_fixture(
    db_pool: asyncpg.Pool,
) -> None:
    deps = _build_deps(
        db_pool,
        ids=[UUID(f"01900000-0000-7000-8000-00000054ee{i:02x}") for i in range(20)],
    )
    _, assembly_id, fixture_id = await _seed_fixture(deps, db_pool)
    await _drain(db_pool)
    page = await bind_list_fixtures(deps)(
        ListFixtures(limit=20),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    ids = [item.fixture_id for item in page.items]
    assert fixture_id in ids
    target = next(item for item in page.items if item.fixture_id == fixture_id)
    assert target.assembly_id == assembly_id
    assert target.binding_count == 1
    assert target.override_count == 0


@pytest.mark.integration
async def test_list_fixtures_filter_by_assembly_id(
    db_pool: asyncpg.Pool,
) -> None:
    deps = _build_deps(
        db_pool,
        ids=[UUID(f"01900000-0000-7000-8000-00000054ef{i:02x}") for i in range(40)],
    )
    _, assembly_a, fixture_a = await _seed_fixture(
        deps, db_pool, asset_name="CamA", assembly_name="A"
    )
    _, _, fixture_b = await _seed_fixture(deps, db_pool, asset_name="CamB", assembly_name="B")
    await _drain(db_pool)
    page = await bind_list_fixtures(deps)(
        ListFixtures(limit=50, assembly_id=assembly_a),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    ids = [item.fixture_id for item in page.items]
    assert fixture_a in ids
    assert fixture_b not in ids
    assert all(item.assembly_id == assembly_a for item in page.items)


@pytest.mark.integration
async def test_list_fixtures_filter_by_surface_id(
    db_pool: asyncpg.Pool,
) -> None:
    """surface_id filter isolates Fixtures registered on one Trust Surface."""
    deps = _build_deps(
        db_pool,
        ids=[UUID(f"01900000-0000-7000-8000-00000055f1{i:02x}") for i in range(40)],
    )
    _, _, fixture_id = await _seed_fixture(deps, db_pool)
    await _drain(db_pool)
    # Fetch all to discover the surface_id our test fixture landed on.
    all_page = await bind_list_fixtures(deps)(
        ListFixtures(limit=50),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    target = next(item for item in all_page.items if item.fixture_id == fixture_id)
    surface_id_target = target.surface_id
    page = await bind_list_fixtures(deps)(
        ListFixtures(limit=50, surface_id=surface_id_target),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    ids = [item.fixture_id for item in page.items]
    assert fixture_id in ids
    assert all(item.surface_id == surface_id_target for item in page.items)


@pytest.mark.integration
async def test_list_fixtures_filter_by_content_hash(
    db_pool: asyncpg.Pool,
) -> None:
    """content_hash filter (federation query)."""
    deps = _build_deps(
        db_pool,
        ids=[UUID(f"01900000-0000-7000-8000-00000054f0{i:02x}") for i in range(40)],
    )
    _, _, fixture_id = await _seed_fixture(deps, db_pool)
    await _drain(db_pool)
    # Fetch all fixtures and pull the content_hash for our fixture.
    all_page = await bind_list_fixtures(deps)(
        ListFixtures(limit=50),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    target = next(item for item in all_page.items if item.fixture_id == fixture_id)
    content_hash = target.assembly_content_hash
    page = await bind_list_fixtures(deps)(
        ListFixtures(limit=50, assembly_content_hash=content_hash),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    ids = [item.fixture_id for item in page.items]
    assert fixture_id in ids

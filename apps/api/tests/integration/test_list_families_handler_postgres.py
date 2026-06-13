"""End-to-end: `list_families` handler against real Postgres
projection table. Stresses the framework against the second
projection in a multi-aggregate BC (alongside Asset's projection).

Family is the simpler projection sibling: 3 events, 3 statuses,
no hierarchy. This pins:

  - FamilyDefined -> status=Defined, version_tag=NULL
  - FamilyVersioned -> status=Versioned, version_tag=payload
  - FamilyDeprecated -> status=Deprecated, version_tag preserved
  - status filter
  - cursor pagination
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.define_family import bind as bind_define
from cora.equipment.features.deprecate_family import DeprecateFamily
from cora.equipment.features.deprecate_family import bind as bind_deprecate
from cora.equipment.features.list_families import ListFamilies
from cora.equipment.features.list_families import bind as bind_list
from cora.equipment.features.version_family import VersionFamily
from cora.equipment.features.version_family import bind as bind_version
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 12, 14, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_define_emits_defined_status_with_null_version_tag(
    db_pool: asyncpg.Pool,
) -> None:
    """Sanity: a freshly defined capability is Defined with version_tag NULL."""
    cap_id = family_stream_id(FamilyName("Continuous Rotation Tomography"))
    deps = _build_deps(db_pool, [uuid4()])
    await bind_define(deps)(
        DefineFamily(name="Continuous Rotation Tomography", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, status, version_tag "
            "FROM proj_equipment_family_summary WHERE family_id = $1",
            cap_id,
        )
    assert row is not None
    assert row["name"] == "Continuous Rotation Tomography"
    assert row["status"] == "Defined"
    assert row["version_tag"] is None


@pytest.mark.integration
async def test_version_writes_versioned_status_and_version_tag(
    db_pool: asyncpg.Pool,
) -> None:
    """Define -> version: status flips Versioned and version_tag lands."""
    cap_id = family_stream_id(FamilyName("Powder Diffraction"))
    deps = _build_deps(db_pool, [uuid4(), uuid4()])
    await bind_define(deps)(
        DefineFamily(name="Powder Diffraction", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionFamily(family_id=cap_id, version_tag="v2.1.0", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, version_tag FROM proj_equipment_family_summary WHERE family_id = $1",
            cap_id,
        )
    assert row is not None
    assert row["status"] == "Versioned"
    assert row["version_tag"] == "v2.1.0"


@pytest.mark.integration
async def test_deprecate_preserves_version_tag(db_pool: asyncpg.Pool) -> None:
    """Define -> version -> deprecate: status flips Deprecated, but
    version_tag stays so the audit trail of "what was the last
    revision before deprecation?" is visible in the projection."""
    cap_id = family_stream_id(FamilyName("X-ray Fluorescence Mapping"))
    deps = _build_deps(db_pool, [uuid4(), uuid4(), uuid4()])
    await bind_define(deps)(
        DefineFamily(name="X-ray Fluorescence Mapping", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionFamily(family_id=cap_id, version_tag="2026-Q3", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_deprecate(deps)(
        DeprecateFamily(family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, version_tag FROM proj_equipment_family_summary WHERE family_id = $1",
            cap_id,
        )
    assert row is not None
    assert row["status"] == "Deprecated"
    assert row["version_tag"] == "2026-Q3"


@pytest.mark.integration
async def test_deprecate_without_version_keeps_version_tag_null(
    db_pool: asyncpg.Pool,
) -> None:
    """Define -> deprecate (skip version): status=Deprecated and
    version_tag stays NULL because nothing ever wrote it."""
    cap_id = family_stream_id(FamilyName("ObsoleteMethod"))
    deps = _build_deps(db_pool, [uuid4(), uuid4()])
    await bind_define(deps)(
        DefineFamily(name="ObsoleteMethod", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_deprecate(deps)(
        DeprecateFamily(family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, version_tag FROM proj_equipment_family_summary WHERE family_id = $1",
            cap_id,
        )
    assert row is not None
    assert row["status"] == "Deprecated"
    assert row["version_tag"] is None


@pytest.mark.integration
async def test_status_filter_returns_only_matching_rows(
    db_pool: asyncpg.Pool,
) -> None:
    """Three capabilities in different statuses; status=Versioned
    returns only the one Versioned row."""
    versioned_id = family_stream_id(FamilyName("ToBeVersioned"))
    deprecated_id = family_stream_id(FamilyName("ToBeDeprecated"))
    deps = _build_deps(
        db_pool,
        [
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
            uuid4(),
        ],
    )
    define = bind_define(deps)
    await define(
        DefineFamily(name="DefinedOnly", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define(
        DefineFamily(name="ToBeVersioned", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_version(deps)(
        VersionFamily(family_id=versioned_id, version_tag="v1", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define(
        DefineFamily(name="ToBeDeprecated", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_deprecate(deps)(
        DeprecateFamily(family_id=deprecated_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)
    handler = bind_list(deps)
    page = await handler(
        ListFamilies(status="Versioned", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].family_id == versioned_id
    assert page.items[0].status == "Versioned"
    assert page.items[0].version_tag == "v1"


@pytest.mark.integration
async def test_cursor_walks_pages(db_pool: asyncpg.Pool) -> None:
    """5 defined capabilities; cursor walks 3 pages with limit=2."""
    cap_ids: list[UUID] = []
    fixed_ids: list[UUID] = []
    for i in range(5):
        cap_ids.append(family_stream_id(FamilyName(f"Cap{i:02d}")))
        fixed_ids.append(uuid4())
    deps = _build_deps(db_pool, fixed_ids)
    define = bind_define(deps)
    for i in range(5):
        await define(
            DefineFamily(name=f"Cap{i:02d}", affordances=frozenset()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await _drain(db_pool)
    handler = bind_list(deps)

    page1 = await handler(
        ListFamilies(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page2 = await handler(
        ListFamilies(cursor=page1.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page3 = await handler(
        ListFamilies(cursor=page2.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 2 and page2.next_cursor is not None
    assert len(page3.items) == 1 and page3.next_cursor is None
    seen = {item.family_id for p in (page1, page2, page3) for item in p.items}
    assert seen == set(cap_ids)


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListFamilies(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None

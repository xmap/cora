"""End-to-end: `list_datasets` handler against real Postgres
projection table. Mirrors the `test_list_assets_handler_postgres.py`
shape: empty page, status filter (Registered vs Discarded), and
cursor pagination walking >limit rows.

The unit suite stubs `deps.pool = None` and only exercises the
empty-page fast path; the entire `async with deps.pool.acquire()`
read branch was uncovered until this file landed (13 lines, 1
partial branch).

Datasets here use no producing_run / subject / derived_from refs:
the handler's three filter columns (`status`, `producing_run_id`,
`subject_id`) are bound into the SQL whether the caller passes
them or not, so the no-ref shape is sufficient to cover every
handler line. Filter-narrowing semantics are pinned by the
contract suite at the route level.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data._projections import register_data_projections
from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
)
from cora.data.features.discard_dataset import DiscardDataset
from cora.data.features.discard_dataset import bind as bind_discard
from cora.data.features.list_datasets import ListDatasets
from cora.data.features.list_datasets import bind as bind_list
from cora.data.features.register_dataset import RegisterDataset
from cora.data.features.register_dataset import bind as bind_register
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 14, 16, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


def _register_command(name: str) -> RegisterDataset:
    """Minimal RegisterDataset: no producing_run / subject / derived_from
    refs so the cross-aggregate pre-loads in the handler short-circuit
    and the test stays focused on the read-side projection + handler."""
    return RegisterDataset(
        name=name,
        uri=f"s3://bucket/{name}",
        checksum_algorithm="sha256",
        checksum_value=_GOOD_SHA256,
        byte_size=1024,
        media_type="application/x-hdf5",
    )


@pytest.mark.integration
async def test_empty_table_returns_empty_page(db_pool: asyncpg.Pool) -> None:
    deps = _build_deps(db_pool, [])
    handler = bind_list(deps)
    page = await handler(
        ListDatasets(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert page.items == []
    assert page.next_cursor is None


@pytest.mark.integration
async def test_register_lands_in_projection(db_pool: asyncpg.Pool) -> None:
    """Sanity: a registered Dataset projects with status=Registered
    and round-trips name + uri."""
    dataset_id = uuid4()
    deps = _build_deps(db_pool, [dataset_id, uuid4()])
    await bind_register(deps)(
        _register_command("scan-001"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    handler = bind_list(deps)
    page = await handler(
        ListDatasets(limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    assert page.items[0].dataset_id == dataset_id
    assert page.items[0].name == "scan-001"
    assert page.items[0].uri == "s3://bucket/scan-001"
    assert page.items[0].status == "Registered"
    assert page.next_cursor is None


@pytest.mark.integration
async def test_status_filter_narrows_registered_vs_discarded(
    db_pool: asyncpg.Pool,
) -> None:
    """Two Datasets, discard one. status=Registered returns the live
    one; status=Discarded returns the discarded one. Pins the
    `$2::text IS NULL OR status = $2` filter SQL."""
    live_id = uuid4()
    dead_id = uuid4()
    deps = _build_deps(db_pool, [live_id, uuid4(), dead_id, uuid4(), uuid4()])
    register = bind_register(deps)
    await register(
        _register_command("live"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register(
        _register_command("dead"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await bind_discard(deps)(
        DiscardDataset(dataset_id=dead_id, reason="superseded by reprocess"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    handler = bind_list(deps)
    registered_page = await handler(
        ListDatasets(status="Registered", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {item.dataset_id for item in registered_page.items} == {live_id}

    discarded_page = await handler(
        ListDatasets(status="Discarded", limit=10),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {item.dataset_id for item in discarded_page.items} == {dead_id}
    assert discarded_page.items[0].status == "Discarded"


@pytest.mark.integration
async def test_cursor_walks_pages(db_pool: asyncpg.Pool) -> None:
    """5 Datasets, limit=2: walk 3 pages with cursors. Covers the
    `_LIST_WITH_CURSOR_SQL` branch and `next_cursor` build."""
    dataset_ids: list[UUID] = []
    fixed_ids: list[UUID] = []
    for _ in range(5):
        ds_id = uuid4()
        dataset_ids.append(ds_id)
        fixed_ids.extend([ds_id, uuid4()])
    deps = _build_deps(db_pool, fixed_ids)
    register = bind_register(deps)
    for i in range(5):
        await register(
            _register_command(f"scan-{i:02d}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    await _drain(db_pool)
    handler = bind_list(deps)

    page1 = await handler(
        ListDatasets(limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page2 = await handler(
        ListDatasets(cursor=page1.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    page3 = await handler(
        ListDatasets(cursor=page2.next_cursor, limit=2),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2 and page1.next_cursor is not None
    assert len(page2.items) == 2 and page2.next_cursor is not None
    assert len(page3.items) == 1 and page3.next_cursor is None
    seen = {item.dataset_id for p in (page1, page2, page3) for item in p.items}
    assert seen == set(dataset_ids)

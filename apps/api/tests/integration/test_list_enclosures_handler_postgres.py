"""End-to-end integration test: list_enclosures + projection round-trip.

Seeds 3 Enclosures via register / observe / decommission handlers,
drains the projection worker, then queries list_enclosures and
verifies:
  - all 3 surface in the projection
  - lifecycle filter narrows correctly
  - permit_status filter narrows correctly
  - facility_code filter narrows correctly
  - cursor pagination produces disjoint pages whose union is complete
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.enclosure._projections import register_enclosure_projections
from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    EnclosurePermitStatus,
    MonitorRef,
)
from cora.enclosure.features import (
    decommission_enclosure,
    list_enclosures,
    observe_enclosure_status,
    register_enclosure,
)
from cora.enclosure.features.decommission_enclosure import DecommissionEnclosure
from cora.enclosure.features.list_enclosures import ListEnclosures
from cora.enclosure.features.observe_enclosure_status import ObserveEnclosureStatus
from cora.enclosure.features.register_enclosure import RegisterEnclosure
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.identity import MonitorSourceId
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_T0 = datetime(2026, 6, 9, 10, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-00000000e003"))


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_enclosure_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _seed(deps: Kernel, *, name: str, facility_code: str = "cora") -> UUID:
    return await register_enclosure.bind(deps)(
        RegisterEnclosure(name=name, facility_code=facility_code),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _observe(deps: Kernel, *, enclosure_id: UUID, new_status: EnclosurePermitStatus) -> None:
    await observe_enclosure_status.bind(deps)(
        ObserveEnclosureStatus(
            enclosure_id=EnclosureId(enclosure_id),
            new_status=new_status,
            reason="interlock chain walkdown",
            monitor_source_id=_MONITOR_SOURCE_ID,
            monitor_ref=MonitorRef(source_kind="EpicsPv", source_id="2bm:hutch:permit"),
            trigger="Monitor",
            observed_at=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _decommission(deps: Kernel, *, enclosure_id: UUID) -> None:
    await decommission_enclosure.bind(deps)(
        DecommissionEnclosure(enclosure_id=EnclosureId(enclosure_id), reason="end-of-life"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_list_enclosures_full_filter_matrix_postgres(db_pool: asyncpg.Pool) -> None:
    suffix = uuid4().hex[:8]
    fc_aps = "cora"
    fc_als = f"als-{suffix}"
    deps = build_postgres_deps(db_pool, now=_T0, ids=[uuid4() for _ in range(30)])
    deps.facility_lookup.register(  # type: ignore[attr-defined]
        facility_id=uuid4(), code=fc_als, kind="Site", status="Active"
    )

    # e1: registered at "cora", never observed (Unknown, Active).
    e1_id = await _seed(deps, name=f"hutch-e1-{suffix}", facility_code=fc_aps)

    # e2: registered at "cora", observed Permitted (Active).
    e2_id = await _seed(deps, name=f"hutch-e2-{suffix}", facility_code=fc_aps)
    await _observe(deps, enclosure_id=e2_id, new_status=EnclosurePermitStatus.PERMITTED)

    # e3: registered at the second facility, observed NotPermitted, then decommissioned.
    e3_id = await _seed(deps, name=f"hutch-e3-{suffix}", facility_code=fc_als)
    await _observe(deps, enclosure_id=e3_id, new_status=EnclosurePermitStatus.NOT_PERMITTED)
    await _decommission(deps, enclosure_id=e3_id)

    await _drain(db_pool)

    handler = list_enclosures.bind(deps)

    # All 3 returned with no filter.
    page = await handler(
        ListEnclosures(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    ids = {item.enclosure_id for item in page.items}
    assert {e1_id, e2_id, e3_id}.issubset(ids)

    # lifecycle=Decommissioned narrows to e3 only.
    page = await handler(
        ListEnclosures(lifecycle="Decommissioned"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    decommissioned_ids = {item.enclosure_id for item in page.items}
    assert e3_id in decommissioned_ids
    assert e1_id not in decommissioned_ids
    assert e2_id not in decommissioned_ids

    # permit_status=Permitted narrows to e2 only.
    page = await handler(
        ListEnclosures(permit_status="Permitted"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    permitted_ids = {item.enclosure_id for item in page.items}
    assert permitted_ids == {e2_id}

    # facility_code narrows to the second facility's enclosure (e3) only.
    page = await handler(
        ListEnclosures(facility_code=fc_als),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert {item.enclosure_id for item in page.items} == {e3_id}

    # e3's row carries both the CORA-clock and decommission fields; e1's carry neither.
    e3_item = next(item for item in page.items if item.enclosure_id == e3_id)
    assert e3_item.last_permit_status_changed_at is not None
    assert e3_item.decommissioned_at is not None
    all_page = await handler(
        ListEnclosures(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    e1_item = next(item for item in all_page.items if item.enclosure_id == e1_id)
    assert e1_item.last_permit_status_changed_at is None
    assert e1_item.decommissioned_at is None


@pytest.mark.integration
async def test_list_enclosures_cursor_pagination_postgres(db_pool: asyncpg.Pool) -> None:
    """Pagination invariants: page size, non-null cursor mid-page, disjoint pages,
    union covers all 3 created."""
    suffix = uuid4().hex[:8]
    fc = f"pgn-{suffix}"
    deps = build_postgres_deps(db_pool, now=_T0, ids=[uuid4() for _ in range(30)])
    deps.facility_lookup.register(  # type: ignore[attr-defined]
        facility_id=uuid4(), code=fc, kind="Site", status="Active"
    )

    seeded_ids: list[UUID] = []
    for i in range(3):
        eid = await _seed(deps, name=f"hutch-pg-{i}-{suffix}", facility_code=fc)
        seeded_ids.append(eid)

    await _drain(db_pool)

    handler = list_enclosures.bind(deps)
    # Page 1: limit=2, scoped to this test's facility.
    page1 = await handler(
        ListEnclosures(limit=2, facility_code=fc),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page1.items) == 2
    assert page1.next_cursor is not None
    page1_ids = {item.enclosure_id for item in page1.items}

    # Page 2: continue with cursor.
    page2 = await handler(
        ListEnclosures(cursor=page1.next_cursor, limit=2, facility_code=fc),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page2.items) == 1
    page2_ids = {item.enclosure_id for item in page2.items}

    # Disjoint pages, union covers all 3 seeds.
    assert page1_ids.isdisjoint(page2_ids)
    assert page1_ids | page2_ids == set(seeded_ids)

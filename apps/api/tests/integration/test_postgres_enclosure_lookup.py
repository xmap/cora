"""Integration tests for `PostgresEnclosureLookup` against a real Postgres.

Pins the cross-stream query contract under the real Enclosure
projection: seeds enclosures via `register_enclosure` (and the
`observe_enclosure_status` / `decommission_enclosure` handlers),
drains the projection worker, then queries through the adapter and
verifies the result matches the seeded enclosures. None-on-missing
semantics are pinned via an unseeded id, and the `find_for_assets`
filter is pinned against multiple containing assets plus the
lifecycle=Active partial-index posture so Decommissioned rows do
not leak into the gate-permit query path.

Closes the EXEMPT_FROM_INTEGRATION gap recorded against the register slice.

Mirrors `test_postgres_credential_lookup.py` and
`test_postgres_facility_lookup.py` (single-row by-id + None-on-missing)
and `test_postgres_supply_lookup.py` (collection-by-criterion +
Decommission-exclusion).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.enclosure._projections import register_enclosure_projections
from cora.enclosure.adapters import PostgresEnclosureLookup
from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    EnclosureLifecycle,
    EnclosurePermitStatus,
    MonitorRef,
)
from cora.enclosure.features import (
    decommission_enclosure,
    observe_enclosure_status,
    register_enclosure,
)
from cora.enclosure.features.decommission_enclosure import DecommissionEnclosure
from cora.enclosure.features.observe_enclosure_status import ObserveEnclosureStatus
from cora.enclosure.features.register_enclosure import RegisterEnclosure
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.identity import MonitorSourceId
from tests.integration._helpers import build_postgres_deps

_T0 = datetime(2026, 6, 9, 10, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 6, 9, 11, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-00000000e001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-00000000e002")
_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-00000000e003"))


async def _drain_enclosure(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_enclosure_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_enclosure(db_pool: asyncpg.Pool, *, name: str, containing_asset_id: UUID) -> UUID:
    deps = build_postgres_deps(db_pool, now=_T0, ids=[uuid4() for _ in range(5)])
    return await register_enclosure.bind(deps)(
        RegisterEnclosure(name=name, containing_asset_id=containing_asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _observe(
    db_pool: asyncpg.Pool, *, enclosure_id: UUID, new_status: EnclosurePermitStatus, now: datetime
) -> None:
    deps = build_postgres_deps(db_pool, now=now, ids=[uuid4() for _ in range(3)])
    await observe_enclosure_status.bind(deps)(
        ObserveEnclosureStatus(
            enclosure_id=EnclosureId(enclosure_id),
            new_status=new_status,
            reason="interlock chain walkdown",
            monitor_source_id=_MONITOR_SOURCE_ID,
            monitor_ref=MonitorRef(source_kind="EpicsPv", source_id="2bm:hutch:permit"),
            trigger="Monitor",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


async def _decommission(db_pool: asyncpg.Pool, *, enclosure_id: UUID, now: datetime) -> None:
    deps = build_postgres_deps(db_pool, now=now, ids=[uuid4() for _ in range(3)])
    await decommission_enclosure.bind(deps)(
        DecommissionEnclosure(enclosure_id=EnclosureId(enclosure_id), reason="end-of-life"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_lookup_unknown_id_returns_none(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresEnclosureLookup(db_pool)
    assert await lookup.lookup(uuid4()) is None


@pytest.mark.integration
async def test_lookup_returns_populated_reference_for_registered_enclosure(
    db_pool: asyncpg.Pool,
) -> None:
    """Genesis INSERT: status=Unknown (universal industrial default),
    lifecycle=Active."""
    suffix = uuid4().hex[:8]
    asset_id = uuid4()
    name = f"hutch-A-{suffix}"
    enclosure_id = await _seed_enclosure(db_pool, name=name, containing_asset_id=asset_id)
    await _drain_enclosure(db_pool)

    lookup = PostgresEnclosureLookup(db_pool)
    result = await lookup.lookup(enclosure_id)
    assert result is not None
    assert result.enclosure_id == enclosure_id
    assert result.name == name
    assert result.containing_asset_id == asset_id
    assert result.permit_status == EnclosurePermitStatus.UNKNOWN.value
    assert result.lifecycle == EnclosureLifecycle.ACTIVE.value


@pytest.mark.integration
async def test_lookup_returns_permitted_status_after_observation(db_pool: asyncpg.Pool) -> None:
    suffix = uuid4().hex[:8]
    asset_id = uuid4()
    enclosure_id = await _seed_enclosure(
        db_pool, name=f"hutch-B-{suffix}", containing_asset_id=asset_id
    )
    await _observe(
        db_pool, enclosure_id=enclosure_id, new_status=EnclosurePermitStatus.PERMITTED, now=_T1
    )
    await _drain_enclosure(db_pool)

    lookup = PostgresEnclosureLookup(db_pool)
    result = await lookup.lookup(enclosure_id)
    assert result is not None
    assert result.permit_status == EnclosurePermitStatus.PERMITTED.value
    assert result.lifecycle == EnclosureLifecycle.ACTIVE.value


@pytest.mark.integration
async def test_lookup_isolates_records_by_id(db_pool: asyncpg.Pool) -> None:
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]
    asset_a, asset_b = uuid4(), uuid4()
    enc_a = await _seed_enclosure(db_pool, name=f"hutch-A-{suffix_a}", containing_asset_id=asset_a)
    enc_b = await _seed_enclosure(db_pool, name=f"hutch-B-{suffix_b}", containing_asset_id=asset_b)
    await _observe(db_pool, enclosure_id=enc_a, new_status=EnclosurePermitStatus.PERMITTED, now=_T1)
    await _observe(
        db_pool, enclosure_id=enc_b, new_status=EnclosurePermitStatus.NOT_PERMITTED, now=_T1
    )
    await _drain_enclosure(db_pool)

    lookup = PostgresEnclosureLookup(db_pool)
    row_a = await lookup.lookup(enc_a)
    row_b = await lookup.lookup(enc_b)
    assert row_a is not None and row_a.permit_status == EnclosurePermitStatus.PERMITTED.value
    assert row_b is not None and row_b.permit_status == EnclosurePermitStatus.NOT_PERMITTED.value


@pytest.mark.integration
async def test_lookup_returns_decommissioned_lifecycle(db_pool: asyncpg.Pool) -> None:
    """`lookup` returns rows in every lifecycle; the caller partitions.
    `find_for_assets` excludes Decommissioned, but `lookup` does not."""
    suffix = uuid4().hex[:8]
    asset_id = uuid4()
    enc = await _seed_enclosure(db_pool, name=f"hutch-tomb-{suffix}", containing_asset_id=asset_id)
    await _decommission(db_pool, enclosure_id=enc, now=_T2)
    await _drain_enclosure(db_pool)

    lookup = PostgresEnclosureLookup(db_pool)
    result = await lookup.lookup(enc)
    assert result is not None
    assert result.lifecycle == EnclosureLifecycle.DECOMMISSIONED.value


@pytest.mark.integration
async def test_find_for_assets_returns_enclosures_for_matching_asset(db_pool: asyncpg.Pool) -> None:
    suffix = uuid4().hex[:8]
    asset_target, asset_other = uuid4(), uuid4()
    enc_a = await _seed_enclosure(
        db_pool, name=f"hutch-target-A-{suffix}", containing_asset_id=asset_target
    )
    enc_b = await _seed_enclosure(
        db_pool, name=f"hutch-target-B-{suffix}", containing_asset_id=asset_target
    )
    enc_other = await _seed_enclosure(
        db_pool, name=f"hutch-other-{suffix}", containing_asset_id=asset_other
    )
    await _drain_enclosure(db_pool)

    lookup = PostgresEnclosureLookup(db_pool)
    results = await lookup.find_for_assets(asset_ids=frozenset({asset_target}))
    returned = {r.enclosure_id for r in results}
    assert enc_a in returned
    assert enc_b in returned
    assert enc_other not in returned


@pytest.mark.integration
async def test_find_for_assets_empty_input_returns_empty(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresEnclosureLookup(db_pool)
    assert await lookup.find_for_assets(asset_ids=frozenset()) == []


@pytest.mark.integration
async def test_find_for_assets_excludes_decommissioned(db_pool: asyncpg.Pool) -> None:
    """Decommissioned enclosures must not gate runs; the
    `lifecycle = 'Active'` partial-index posture is respected end-to-end."""
    suffix = uuid4().hex[:8]
    asset_id = uuid4()
    enc_active = await _seed_enclosure(
        db_pool, name=f"hutch-active-{suffix}", containing_asset_id=asset_id
    )
    enc_tomb = await _seed_enclosure(
        db_pool, name=f"hutch-tomb-{suffix}", containing_asset_id=asset_id
    )
    await _decommission(db_pool, enclosure_id=enc_tomb, now=_T2)
    await _drain_enclosure(db_pool)

    lookup = PostgresEnclosureLookup(db_pool)
    results = await lookup.find_for_assets(asset_ids=frozenset({asset_id}))
    returned = {r.enclosure_id for r in results}
    assert enc_active in returned
    assert enc_tomb not in returned

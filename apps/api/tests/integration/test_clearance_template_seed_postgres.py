"""Integration tests for the Safety BC's `seed_clearance_templates` lifespan hook.

Pinned:
- Happy path: against a Postgres pool with the bootstrap-seeded
  self-Facility row visible in `proj_federation_facility_summary`, a
  single seed call writes `len(TEN_FORM_TYPES) * 2` ClearanceTemplate
  events (Define + Activate per template) and the projection lands
  `len(TEN_FORM_TYPES)` rows -- all in `status='Active'`. Proves the
  end-to-end seed + projection convergence under real Postgres.
- Idempotency: a second seed call against the same db_pool MUST NOT
  duplicate events or projection rows. Anchored on the deterministic
  `clearance_template_stream_id(facility_code, template_code)`
  derivation; the second-pass `expected_version=0` append surfaces
  ConcurrencyError, which the hook swallows as "already_present".
- Deterministic stream ids: for every (facility, template_code) pair,
  `event_store.load("ClearanceTemplate", clearance_template_stream_id(
  facility.code.value, template_code))` returns exactly two events in
  the locked order: ClearanceTemplateDefined then
  ClearanceTemplateActivated. Pins the per-pair atomic two-event write.
- No-facilities short-circuit: when `FacilityLookup.list_active()`
  returns an empty Sequence (the master memo's no-active-Facility
  branch -- exercised here by injecting an empty
  `InMemoryFacilityLookup`), the seed call writes zero ClearanceTemplate
  events. Proves the fan-out is properly guarded at the outer loop.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation import register_federation_projections
from cora.infrastructure.adapters.in_memory_facility_lookup import InMemoryFacilityLookup
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.safety import register_safety_projections, seed_clearance_templates
from cora.safety._clearance_template_seed import TEN_FORM_TYPES
from cora.safety.aggregates.clearance_template import (
    clearance_template_stream_id,
    from_stored,
)
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-0000000c70e2")
_SELF_FACILITY_CODE = "cora"


async def _drain_federation(db_pool: asyncpg.Pool) -> None:
    """Pump Federation-owned projections so the bootstrap self-Facility
    row lands in `proj_federation_facility_summary`; the seed hook's
    `kernel.facility_lookup.list_active()` reads that projection when
    `PostgresFacilityLookup` is wired."""
    registry = ProjectionRegistry()
    register_federation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _drain_safety(db_pool: asyncpg.Pool) -> None:
    """Pump Safety-owned projections so the seed's
    ClearanceTemplateDefined + ClearanceTemplateActivated events land
    in `proj_safety_clearance_template_summary`."""
    registry = ProjectionRegistry()
    register_safety_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_seed_clearance_templates_writes_ten_pairs_per_active_facility(
    db_pool: asyncpg.Pool,
) -> None:
    """One seed call against the lifespan-seeded self-Facility writes
    exactly `len(TEN_FORM_TYPES) * 2` ClearanceTemplate events (Define
    + Activate per template) and the projection lands
    `len(TEN_FORM_TYPES)` Active rows under `facility_code='cora'`."""
    await _drain_federation(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(200)])

    await seed_clearance_templates(deps)
    await _drain_safety(db_pool)

    event_count = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'ClearanceTemplate'"
    )
    assert event_count == len(TEN_FORM_TYPES) * 2

    projection_count = await db_pool.fetchval(
        """
        SELECT count(*) FROM proj_safety_clearance_template_summary
        WHERE facility_code = $1
        """,
        _SELF_FACILITY_CODE,
    )
    assert projection_count == len(TEN_FORM_TYPES)

    non_active = await db_pool.fetchval(
        """
        SELECT count(*) FROM proj_safety_clearance_template_summary
        WHERE facility_code = $1 AND status <> 'Active'
        """,
        _SELF_FACILITY_CODE,
    )
    assert non_active == 0


@pytest.mark.integration
async def test_seed_clearance_templates_is_idempotent_across_calls(
    db_pool: asyncpg.Pool,
) -> None:
    """A second seed call against the same db_pool MUST NOT duplicate
    events or projection rows; the hook swallows the
    expected_version=0 ConcurrencyError as the "already seeded"
    signal."""
    await _drain_federation(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(200)])

    await seed_clearance_templates(deps)
    await seed_clearance_templates(deps)
    await _drain_safety(db_pool)

    event_count = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'ClearanceTemplate'"
    )
    assert event_count == len(TEN_FORM_TYPES) * 2

    projection_count = await db_pool.fetchval(
        """
        SELECT count(*) FROM proj_safety_clearance_template_summary
        WHERE facility_code = $1
        """,
        _SELF_FACILITY_CODE,
    )
    assert projection_count == len(TEN_FORM_TYPES)


@pytest.mark.integration
async def test_seed_clearance_templates_uses_deterministic_stream_ids(
    db_pool: asyncpg.Pool,
) -> None:
    """For every (facility, template_code) pair, the seed writes to the
    deterministic stream id derived from `clearance_template_stream_id(
    facility_code, template_code)`; loading that stream returns exactly
    two events in the locked order: Defined then Activated."""
    await _drain_federation(db_pool)

    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(200)])

    await seed_clearance_templates(deps)

    facilities = await deps.facility_lookup.list_active()
    assert len(facilities) >= 1

    for facility in facilities:
        for template_code in TEN_FORM_TYPES:
            stream_id = clearance_template_stream_id(facility.code.value, template_code)
            events, version = await deps.event_store.load("ClearanceTemplate", stream_id)
            assert version == 2
            assert len(events) == 2

            first = from_stored(events[0])
            second = from_stored(events[1])
            assert type(first).__name__ == "ClearanceTemplateDefined"
            assert type(second).__name__ == "ClearanceTemplateActivated"
            # Both events agree on the deterministic stream_id.
            assert first.template_id == stream_id  # type: ignore[union-attr]
            assert second.template_id == stream_id  # type: ignore[union-attr]


@pytest.mark.integration
async def test_seed_clearance_templates_skips_when_no_active_facilities(
    db_pool: asyncpg.Pool,
) -> None:
    """When `FacilityLookup.list_active()` returns an empty Sequence,
    the seed writes zero ClearanceTemplate events; the outer loop
    short-circuits before any per-template write attempt. Exercised by
    injecting an empty `InMemoryFacilityLookup` (the bootstrap
    self-Facility row is bypassed; the in-memory lookup has no
    records)."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        facility_lookup=InMemoryFacilityLookup(),
    )

    await seed_clearance_templates(deps)

    event_count = await db_pool.fetchval(
        "SELECT count(*) FROM events WHERE stream_type = 'ClearanceTemplate'"
    )
    assert event_count == 0

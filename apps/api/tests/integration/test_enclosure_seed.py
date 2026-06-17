"""Integration tests for the config-driven enclosure seeder (`seed_enclosures`).

Pins the seeder contract against a real Postgres projection:
  - empty `enclosure_permit_pvs` -> no-op, `{}`.
  - configured names -> one Active/Unknown enclosure each, under
    `self_facility_code`, returned in the `{name: id}` map.
  - idempotent: a second seed after the projection catches up resolves
    the existing Active enclosure (via `lookup_by_name`) and appends NO
    duplicate genesis event.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest

from cora.enclosure import seed_enclosures
from cora.enclosure._projections import register_enclosure_projections
from cora.enclosure.adapters import PostgresEnclosureLookup
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_T0 = datetime(2026, 6, 17, 10, 0, 0, tzinfo=UTC)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_enclosure_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _deps_with(db_pool: asyncpg.Pool, *, permit_pvs: dict[str, str]) -> Kernel:
    # self_facility_code defaults to "cora", which build_postgres_deps seeds
    # as the Active self-Facility; the seeder writes the genesis raw so it
    # does not resolve the facility, but the projection records "cora".
    deps = build_postgres_deps(db_pool, now=_T0, ids=[uuid4() for _ in range(9)])
    return dataclasses.replace(
        deps,
        settings=Settings(app_env="test", enclosure_permit_pvs=permit_pvs),  # type: ignore[call-arg]
        enclosure_lookup=PostgresEnclosureLookup(db_pool),
    )


@pytest.mark.integration
async def test_seed_enclosures_empty_config_is_noop(db_pool: asyncpg.Pool) -> None:
    deps = _deps_with(db_pool, permit_pvs={})
    assert await seed_enclosures(deps) == {}


@pytest.mark.integration
async def test_seed_enclosures_registers_active_unknown(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-seed-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "S02BM-PSS:StaA:SecureM"})

    result = await seed_enclosures(deps)
    assert name in result
    enclosure_id = result[name]
    await _drain(db_pool)

    row = await PostgresEnclosureLookup(db_pool).lookup_by_name(facility_code="cora", name=name)
    assert row is not None
    assert row.enclosure_id == enclosure_id
    assert row.permit_status == "Unknown"
    assert row.lifecycle == "Active"


@pytest.mark.integration
async def test_seed_enclosures_idempotent_no_duplicate_event(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-idem-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "S02BM-PSS:StaA:SecureM"})
    first = await seed_enclosures(deps)
    enclosure_id = first[name]
    await _drain(db_pool)

    # Second boot: the projection now reflects the Active enclosure, so the
    # pre-check resolves it and the seeder registers nothing new.
    deps2 = _deps_with(db_pool, permit_pvs={name: "S02BM-PSS:StaA:SecureM"})
    second = await seed_enclosures(deps2)
    assert second[name] == enclosure_id

    events, _ = await deps.event_store.load("Enclosure", enclosure_id)
    registered = [e for e in events if e.event_type == "EnclosureRegistered"]
    assert len(registered) == 1

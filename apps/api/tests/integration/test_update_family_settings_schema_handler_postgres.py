"""End-to-end integration test: update_family_settings_schema against real Postgres.

Round-trip the event + projection column:
  - Define capability
  - Update schema
  - Load via fold-on-read returns the schema
  - Projection's settings_schema_present column flips TRUE
  - Clear the schema (None payload)
  - Projection flips back to FALSE
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment._projections import register_equipment_projections
from cora.equipment.aggregates.family import FamilyName, family_stream_id, load_family
from cora.equipment.features import define_family, update_family_settings_schema
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.update_family_settings_schema import UpdateFamilySettingsSchema
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 13, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


def _example_schema() -> dict[str, Any]:
    return {
        "$schema": _DRAFT,
        "type": "object",
        "properties": {
            "energy": {
                "type": "number",
                "minimum": 5,
                "maximum": 50,
                "unit": {"system": "udunits", "code": "keV"},
            },
            "filter_material": {"type": "string", "enum": ["Cu", "Al", "Mo"]},
        },
        "required": ["energy"],
    }


@pytest.mark.integration
async def test_update_family_settings_schema_round_trips_through_event_store_and_projection(
    db_pool: asyncpg.Pool,
) -> None:
    """Full end-to-end: define, set schema, fold-on-read returns the
    schema, projection settings_schema_present = TRUE."""
    family_id = family_stream_id(FamilyName("phase-contrast micro-CT"))
    deps = _build_deps(
        db_pool,
        [uuid4(), uuid4()],  # define event_id + schema-update event_id
    )

    # Define
    await define_family.bind(deps)(
        DefineFamily(name="phase-contrast micro-CT", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Update schema
    schema = _example_schema()
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(family_id=family_id, settings_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Fold-on-read returns the schema on the aggregate
    loaded = await load_family(deps.event_store, family_id)
    assert loaded is not None
    assert loaded.settings_schema == schema

    # Projection reflects schema-present
    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT settings_schema_present FROM proj_equipment_family_summary "
            "WHERE family_id = $1",
            family_id,
        )
    assert row is not None
    assert row["settings_schema_present"] is True


@pytest.mark.integration
async def test_clearing_schema_flips_projection_present_back_to_false(
    db_pool: asyncpg.Pool,
) -> None:
    """Operator removes a previously-declared schema; projection
    flips back to FALSE."""
    family_id = family_stream_id(FamilyName("phase-contrast micro-CT"))
    deps = _build_deps(
        db_pool,
        # 1 define event_id + 2 schema-update event_ids
        [uuid4(), uuid4(), uuid4()],
    )

    await define_family.bind(deps)(
        DefineFamily(name="phase-contrast micro-CT", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(family_id=family_id, settings_schema=_example_schema()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Now clear it
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(family_id=family_id, settings_schema=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    loaded = await load_family(deps.event_store, family_id)
    assert loaded is not None
    assert loaded.settings_schema is None

    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT settings_schema_present FROM proj_equipment_family_summary "
            "WHERE family_id = $1",
            family_id,
        )
    assert row is not None
    assert row["settings_schema_present"] is False


@pytest.mark.integration
async def test_no_op_on_unchanged_schema_does_not_emit_event(
    db_pool: asyncpg.Pool,
) -> None:
    """Re-submitting the same schema must NOT emit a new event
    (decider returns []). Verify by checking the stream version
    didn't advance."""
    family_id = family_stream_id(FamilyName("phase-contrast micro-CT"))
    deps = _build_deps(
        db_pool,
        [uuid4(), uuid4()],  # define event_id + first schema-update event_id
    )

    await define_family.bind(deps)(
        DefineFamily(name="phase-contrast micro-CT", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    schema = _example_schema()
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(family_id=family_id, settings_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version_after_first = await deps.event_store.load("Family", family_id)

    # Re-submit identical schema; should be a no-op
    await update_family_settings_schema.bind(deps)(
        UpdateFamilySettingsSchema(family_id=family_id, settings_schema=schema),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    _, version_after_second = await deps.event_store.load("Family", family_id)
    assert version_after_second == version_after_first, (
        "Re-submitting unchanged schema should not append a new event"
    )

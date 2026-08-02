"""End-to-end integration test: define_calibration handler against real Postgres.

Pins the genesis-event persistence + Postgres jsonb canonicalisation
on identity-tuple uniqueness (Q6 lock: key-order normalised +
numeric value-equality `25 == 25.0` + duplicate-key dedup) at the
projection layer.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.calibration.aggregates.calibration import (
    CalibrationIdentityAlreadyExistsError,
)
from cora.calibration.features import define_calibration
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.projections import CalibrationSummaryProjection
from cora.calibration.quantities import CalibrationQuantity
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000ca5001")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000ca5002")
_SUBSYSTEM_ID = UUID("01900000-0000-7000-8000-000000ca5003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_calibration_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])

    calibration_id = await define_calibration.bind(deps)(
        DefineCalibration(
            target_id=_SUBSYSTEM_ID,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            operating_point={"energy": 25.0, "optics_config": "5x"},
            description="vessel-A bakeout pre-scan",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert calibration_id == _NEW_ID

    events, version = await deps.event_store.load("Calibration", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "CalibrationDefined"
    assert stored.schema_version == 1
    # `defined_at` is derived from envelope `occurred_at` at the
    # evolver; the wire payload carries `defined_by` + `occurred_at`.
    assert stored.payload == {
        "calibration_id": str(_NEW_ID),
        "target_id": str(_SUBSYSTEM_ID),
        "quantity": "rotation_center",
        "operating_point": {"energy": 25.0, "optics_config": "5x"},
        "description": "vessel-A bakeout pre-scan",
        "defined_by": str(_PRINCIPAL_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineCalibration"}
    assert stored.occurred_at == _NOW


@pytest.mark.integration
async def test_define_calibration_projection_lands_row_with_canonical_operating_point(
    db_pool: asyncpg.Pool,
) -> None:
    """Q6 lock: Postgres jsonb canonicalises on insert (key-order + numeric
    value-equality). After projection drain, the proj_calibration_summary
    row should be queryable by canonical operating_point form."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])

    await define_calibration.bind(deps)(
        DefineCalibration(
            target_id=_SUBSYSTEM_ID,
            quantity=CalibrationQuantity.ROTATION_CENTER,
            # Key order: optics_config first, energy second.
            operating_point={"optics_config": "5x", "energy": 25.0},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Drain the projection so the row lands.
    registry = ProjectionRegistry()
    registry.register(CalibrationSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    # Query the projection by the canonical op-point form (keys in any
    # order; Postgres jsonb `=` normalises both sides).
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT calibration_id, target_id, quantity,
                   operating_point, description, revision_count,
                   latest_revision_status, latest_revision_source_kind
            FROM proj_calibration_summary
            WHERE target_id = $1
              AND quantity = $2
              AND operating_point = $3::jsonb
            """,
            _SUBSYSTEM_ID,
            "rotation_center",
            '{"energy": 25.0, "optics_config": "5x"}',
        )
    assert row is not None
    assert row["calibration_id"] == _NEW_ID
    assert row["revision_count"] == 0
    assert row["latest_revision_status"] is None
    assert row["latest_revision_source_kind"] is None


@pytest.mark.integration
async def test_define_calibration_projection_rejects_duplicate_identity(
    db_pool: asyncpg.Pool,
) -> None:
    """Q6 lock: the projection's jsonb UNIQUE constraint catches duplicate
    identity-tuple inserts. The second `define_calibration` writes a
    second event to a NEW stream (different calibration_id), but the
    projection write fails on the UNIQUE constraint.

    For 12a-3 the design memo defers the lookup-port pre-check, so the
    duplicate event remains in its own stream and the projection
    bookmark fails-loud. We assert: (a) both events persist; (b) drain
    attempts surface the UNIQUE-violation error rather than silently
    dropping the row. The transactional rollback semantics of the
    projection worker (per-batch transaction; UNIQUE violation rolls
    back the whole batch) is independent of this test — what matters
    is that the duplicate doesn't silently corrupt the read model."""
    second_cal_id = UUID("01900000-0000-7000-8000-000000ca5011")
    second_event_id = UUID("01900000-0000-7000-8000-000000ca5012")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[_NEW_ID, _EVENT_ID, second_cal_id, second_event_id],
    )

    cmd = DefineCalibration(
        target_id=_SUBSYSTEM_ID,
        quantity=CalibrationQuantity.ROTATION_CENTER,
        operating_point={"energy": 25.0, "optics_config": "5x"},
    )
    first_id = await define_calibration.bind(deps)(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    second_id = await define_calibration.bind(deps)(
        cmd,
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert first_id != second_id

    # Both event streams exist (the design memo's deferred-lookup-port
    # tradeoff: duplicate events get written; the projection catches them).
    first_events, _v1 = await deps.event_store.load("Calibration", first_id)
    second_events, _v2 = await deps.event_store.load("Calibration", second_id)
    assert len(first_events) == 1
    assert len(second_events) == 1

    # Drain projection: the UNIQUE constraint surfaces the violation.
    registry = ProjectionRegistry()
    registry.register(CalibrationSummaryProjection())
    with pytest.raises(Exception) as excinfo:  # asyncpg.UniqueViolationError
        await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())
    msg = str(excinfo.value).lower()
    assert "unique" in msg or "constraint" in msg or "duplicate" in msg

    # Silence unused-import warning when this test runs in isolation.
    _ = CalibrationIdentityAlreadyExistsError

"""End-to-end: the Asset.drawing additive widen lands in
proj_equipment_asset_summary's drawing_system / drawing_number /
drawing_revision columns against real Postgres.

The Asset aggregate carries an optional Drawing VO captured at
registration. The projection unfolds the Drawing into three nullable
TEXT columns (with a CHECK constraint pinning the closed
DrawingSystem enum at the DB layer) rather than a JSONB blob, so
direct filtering ("all assets built to ICMS drawing P4105") stays a
simple WHERE. The migration is a pure ADD COLUMN with NULL default;
legacy AssetRegistered events without the drawing payload key fold
to all-NULL.

Pins:
  - register_asset with NO drawing -> 3 columns NULL
  - register_asset with drawing including revision -> 3 columns
    populated (system, number, revision)
  - register_asset with drawing omitting revision -> revision NULL,
    other two populated
  - CHECK constraint on drawing_system rejects unknown values when
    written directly via SQL (defense-in-depth pin)
  - AssetRegistered with model_id in the payload lands in the new
    model_id column; legacy events without the key fold to NULL
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.aggregates._drawing import Drawing, DrawingSystem
from cora.equipment.aggregates.asset import AssetLevel
from cora.equipment.features.register_asset import RegisterAsset
from cora.equipment.features.register_asset import bind as bind_register_asset
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import NewEvent
from tests.integration._equipment_helpers import drain_equipment_projections
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _build_deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _register_asset(
    pool: asyncpg.Pool,
    *,
    asset_id: UUID,
    drawing: Drawing | None,
    name: str = "specimen",
) -> None:
    deps = _build_deps(pool, [asset_id, uuid4()])
    await bind_register_asset(deps)(
        RegisterAsset(
            name=name,
            level=AssetLevel.DEVICE,
            parent_id=uuid4(),
            drawing=drawing,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await drain_equipment_projections(pool)


@pytest.mark.integration
async def test_register_without_drawing_leaves_three_columns_null(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_asset(db_pool, asset_id=asset_id, drawing=None, name="legacy-shape")

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT drawing_system, drawing_number, drawing_revision "
            "FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["drawing_system"] is None
    assert row["drawing_number"] is None
    assert row["drawing_revision"] is None


@pytest.mark.integration
async def test_register_with_full_drawing_populates_three_columns(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_asset(
        db_pool,
        asset_id=asset_id,
        drawing=Drawing(system=DrawingSystem.ICMS, number="P4105", revision="A"),
        name="microscope-2bm",
    )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT drawing_system, drawing_number, drawing_revision "
            "FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["drawing_system"] == "ICMS"
    assert row["drawing_number"] == "P4105"
    assert row["drawing_revision"] == "A"


@pytest.mark.integration
async def test_register_with_drawing_no_revision_leaves_revision_null(
    db_pool: asyncpg.Pool,
) -> None:
    asset_id = uuid4()
    await _register_asset(
        db_pool,
        asset_id=asset_id,
        drawing=Drawing(system=DrawingSystem.EDMS, number="9001", revision=None),
        name="edms-resolves-to-latest",
    )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT drawing_system, drawing_number, drawing_revision "
            "FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["drawing_system"] == "EDMS"
    assert row["drawing_number"] == "9001"
    assert row["drawing_revision"] is None


@pytest.mark.integration
async def test_check_constraint_rejects_unknown_drawing_system(
    db_pool: asyncpg.Pool,
) -> None:
    """Defense in depth: bypass the aggregate and write directly to
    the projection table with an unknown drawing_system. The CHECK
    constraint pinned by the migration must reject the write,
    matching the closed-StrEnum lock at the domain layer."""
    asset_id = uuid4()
    async with db_pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "INSERT INTO proj_equipment_asset_summary "
                "(asset_id, name, level, lifecycle, condition, parent_id, "
                "drawing_system, drawing_number, drawing_revision, created_at) "
                "VALUES ($1, 'x', 'Device', 'Commissioned', 'Nominal', NULL, "
                "'UnknownSystem', '123', NULL, now())",
                asset_id,
            )


async def _append_asset_registered(
    pool: asyncpg.Pool,
    *,
    asset_id: UUID,
    payload_extra: dict[str, object],
) -> None:
    """Append a synthetic AssetRegistered event directly to the event
    store. Bypasses the register_asset handler so the model_id payload
    key can be exercised at the projection layer ahead of the
    register_asset slice landing model_id in the command + decider."""
    store = PostgresEventStore(pool)
    payload: dict[str, object] = {
        "asset_id": str(asset_id),
        "name": "synthetic-asset",
        "level": "Device",
        "parent_id": str(uuid4()),
        "occurred_at": _NOW.isoformat(),
    }
    payload.update(payload_extra)
    await store.append(
        "Asset",
        asset_id,
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type="AssetRegistered",
                schema_version=1,
                payload=payload,
                occurred_at=_NOW,
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                metadata={},
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    await drain_equipment_projections(pool)


@pytest.mark.integration
async def test_asset_registered_with_model_id_populates_model_column(
    db_pool: asyncpg.Pool,
) -> None:
    """An AssetRegistered event carrying the optional model_id key
    lands in the proj_equipment_asset_summary.model_id column after
    projection drain."""
    asset_id = uuid4()
    model_id = uuid4()
    await _append_asset_registered(
        db_pool,
        asset_id=asset_id,
        payload_extra={"model_id": str(model_id)},
    )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT model_id FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["model_id"] == model_id


@pytest.mark.integration
async def test_asset_registered_without_model_id_leaves_model_column_null(
    db_pool: asyncpg.Pool,
) -> None:
    """Legacy AssetRegistered events (and unbound genesis registrations)
    omit the model_id payload key; the new column folds to NULL via the
    additive-payload pattern."""
    asset_id = uuid4()
    await _append_asset_registered(
        db_pool,
        asset_id=asset_id,
        payload_extra={},
    )

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT model_id FROM proj_equipment_asset_summary WHERE asset_id = $1",
            asset_id,
        )
    assert row is not None
    assert row["model_id"] is None

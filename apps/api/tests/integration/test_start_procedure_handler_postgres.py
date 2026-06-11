"""End-to-end integration test: start_procedure against real Postgres.

Pinned: ProcedureStarted appends as v2 on the Procedure stream;
cross-aggregate Asset load + Decommissioned guard work end-to-end.
Mirrors the start_run integration test in shape (seeds upstream
Equipment-BC state via real handlers, then targets the new Procedure).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import (
    AssetLifecycle,
    AssetTier,
)
from cora.equipment.features import decommission_asset, register_asset
from cora.equipment.features.decommission_asset import DecommissionAsset
from cora.equipment.features.register_asset import RegisterAsset
from cora.operation.aggregates.procedure import (
    ProcedureCannotStartError,
    ProcedurePlanAssetDecommissionedError,
    ProcedureStatus,
    fold,
    from_stored,
)
from cora.operation.features import register_procedure, start_procedure
from cora.operation.features.register_procedure import RegisterProcedure
from cora.operation.features.start_procedure import StartProcedure
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_start_procedure_persists_event_to_postgres_with_active_target_asset(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy path: register Asset (Active), register Procedure targeting it,
    start the Procedure. Confirms cross-aggregate Asset load works end-to-end."""
    asset_id = UUID("01900000-0000-7000-8000-0000000d0a01")
    asset_event_id = UUID("01900000-0000-7000-8000-0000000d0a02")
    site_id = UUID("01900000-0000-7000-8000-0000000d0a03")
    procedure_id = UUID("01900000-0000-7000-8000-0000000d0a11")
    procedure_event_id = UUID("01900000-0000-7000-8000-0000000d0a12")
    start_event_id = UUID("01900000-0000-7000-8000-0000000d0a13")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            asset_id,
            asset_event_id,
            procedure_id,
            procedure_event_id,
            start_event_id,
        ],
    )

    # Seed Asset (Active by default after register).
    await register_asset.bind(deps)(
        RegisterAsset(name="EigerDetector", tier=AssetTier.DEVICE, parent_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Register Procedure targeting that Asset.
    await register_procedure.bind(deps)(
        RegisterProcedure(
            name="2-BM rotation-axis alignment",
            kind="alignment",
            target_asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Start it.
    await start_procedure.bind(deps)(
        StartProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 2
    assert events[0].event_type == "ProcedureRegistered"
    assert events[1].event_type == "ProcedureStarted"
    assert events[1].event_id == start_event_id
    assert events[1].principal_id == _PRINCIPAL_ID
    assert events[1].correlation_id == _CORRELATION_ID
    assert events[1].payload == {
        "procedure_id": str(procedure_id),
        "occurred_at": _NOW.isoformat(),
    }

    # Round-trip through fold to confirm RUNNING.
    state = fold([from_stored(s) for s in events])
    assert state is not None
    assert state.status is ProcedureStatus.RUNNING
    assert state.target_asset_ids == frozenset({asset_id})


@pytest.mark.integration
async def test_start_procedure_rejects_decommissioned_target_asset_in_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Decommissioned guard is enforced after Asset is loaded from real PG stream."""
    asset_id = UUID("01900000-0000-7000-8000-0000000d0b01")
    asset_event_id = UUID("01900000-0000-7000-8000-0000000d0b02")
    decommission_event_id = UUID("01900000-0000-7000-8000-0000000d0b03")
    site_id = UUID("01900000-0000-7000-8000-0000000d0b04")
    procedure_id = UUID("01900000-0000-7000-8000-0000000d0b11")
    procedure_event_id = UUID("01900000-0000-7000-8000-0000000d0b12")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            asset_id,
            asset_event_id,
            decommission_event_id,
            procedure_id,
            procedure_event_id,
        ],
    )

    await register_asset.bind(deps)(
        RegisterAsset(name="StaleDetector", tier=AssetTier.DEVICE, parent_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await decommission_asset.bind(deps)(
        DecommissionAsset(asset_id=asset_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Verify the Asset is actually Decommissioned at the source.
    from cora.equipment.aggregates.asset import load_asset

    asset = await load_asset(deps.event_store, asset_id)
    assert asset is not None
    assert asset.lifecycle is AssetLifecycle.DECOMMISSIONED

    await register_procedure.bind(deps)(
        RegisterProcedure(
            name="Doomed alignment",
            kind="alignment",
            target_asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    with pytest.raises(ProcedurePlanAssetDecommissionedError) as exc:
        await start_procedure.bind(deps)(
            StartProcedure(procedure_id=procedure_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.asset_ids == [asset_id]

    # No ProcedureStarted appended; stream should be at v1.
    _, version = await deps.event_store.load("Procedure", procedure_id)
    assert version == 1


@pytest.mark.integration
async def test_start_procedure_re_start_raises_in_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Strict-not-idempotent: second start against same Procedure raises."""
    procedure_id = UUID("01900000-0000-7000-8000-0000000d0c01")
    procedure_event_id = UUID("01900000-0000-7000-8000-0000000d0c02")
    start_event_id = UUID("01900000-0000-7000-8000-0000000d0c03")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[procedure_id, procedure_event_id, start_event_id],
    )

    await register_procedure.bind(deps)(
        RegisterProcedure(name="Beam-mode change", kind="beam_mode_change"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_procedure.bind(deps)(
        StartProcedure(procedure_id=procedure_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Re-start: id-pool exhausted, but we still need an event id for the
    # transition the decider would emit IF it weren't for the guard. Since
    # the decider raises before reaching the event-store append, no id is
    # consumed. Re-build deps with a fresh id queue to be safe.
    deps2 = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[UUID("01900000-0000-7000-8000-0000000d0c04")],
    )
    with pytest.raises(ProcedureCannotStartError):
        await start_procedure.bind(deps2)(
            StartProcedure(procedure_id=procedure_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

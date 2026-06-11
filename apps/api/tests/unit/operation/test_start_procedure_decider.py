"""Pure-decider tests for `start_procedure` slice.

Third decider in the codebase that takes upstream aggregate state as
input (after Plan's `define_plan` and Run's `start_run`). Exercises
the decider directly with hand-built `ProcedureStartContext`;
handler-level integration lives in test_start_procedure_handler.py.

Validation order:
  1. State must not be None (ProcedureNotFoundError)
  2. State.status must be Defined (ProcedureCannotStartError)
  3. No target Asset Decommissioned (ProcedurePlanAssetDecommissionedError)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetTier,
)
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureCannotStartError,
    ProcedureName,
    ProcedureNotFoundError,
    ProcedurePlanAssetDecommissionedError,
    ProcedureStarted,
    ProcedureStatus,
)
from cora.operation.features import start_procedure
from cora.operation.features.start_procedure import ProcedureStartContext, StartProcedure

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _procedure(
    *,
    procedure_id: UUID | None = None,
    target_asset_ids: frozenset[UUID] | None = None,
    status: ProcedureStatus = ProcedureStatus.DEFINED,
) -> Procedure:
    return Procedure(
        id=procedure_id or uuid4(),
        name=ProcedureName("Vessel-A bakeout"),
        kind="bakeout",
        target_asset_ids=target_asset_ids if target_asset_ids is not None else frozenset(),
        status=status,
        parent_run_id=None,
    )


def _asset(
    *,
    asset_id: UUID | None = None,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id or uuid4(),
        name=AssetName("EigerDetector"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=lifecycle,
        family_ids=frozenset(),
    )


@pytest.mark.unit
def test_decide_emits_procedure_started_when_defined() -> None:
    proc = _procedure()
    events = start_procedure.decide(
        state=proc,
        command=StartProcedure(procedure_id=proc.id),
        context=ProcedureStartContext(assets={}),
        now=_NOW,
    )
    assert len(events) == 1
    assert isinstance(events[0], ProcedureStarted)
    assert events[0].procedure_id == proc.id
    assert events[0].occurred_at == _NOW


@pytest.mark.unit
def test_decide_accepts_empty_target_assets() -> None:
    """Facility-envelope procedures (beam-mode change) start fine with no targets."""
    proc = _procedure()
    events = start_procedure.decide(
        state=proc,
        command=StartProcedure(procedure_id=proc.id),
        context=ProcedureStartContext(assets={}),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_accepts_active_target_assets() -> None:
    asset = _asset()
    proc = _procedure(target_asset_ids=frozenset({asset.id}))
    events = start_procedure.decide(
        state=proc,
        command=StartProcedure(procedure_id=proc.id),
        context=ProcedureStartContext(assets={asset.id: asset}),
        now=_NOW,
    )
    assert len(events) == 1


@pytest.mark.unit
def test_decide_rejects_when_state_is_none() -> None:
    pid = uuid4()
    with pytest.raises(ProcedureNotFoundError) as exc:
        start_procedure.decide(
            state=None,
            command=StartProcedure(procedure_id=pid),
            context=ProcedureStartContext(assets={}),
            now=_NOW,
        )
    assert exc.value.procedure_id == pid


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    [
        ProcedureStatus.RUNNING,
        ProcedureStatus.COMPLETED,
        ProcedureStatus.ABORTED,
        ProcedureStatus.TRUNCATED,
    ],
)
def test_decide_rejects_non_defined_status(status: ProcedureStatus) -> None:
    proc = _procedure(status=status)
    with pytest.raises(ProcedureCannotStartError) as exc:
        start_procedure.decide(
            state=proc,
            command=StartProcedure(procedure_id=proc.id),
            context=ProcedureStartContext(assets={}),
            now=_NOW,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
def test_decide_rejects_decommissioned_target_asset() -> None:
    asset = _asset(lifecycle=AssetLifecycle.DECOMMISSIONED)
    proc = _procedure(target_asset_ids=frozenset({asset.id}))
    with pytest.raises(ProcedurePlanAssetDecommissionedError) as exc:
        start_procedure.decide(
            state=proc,
            command=StartProcedure(procedure_id=proc.id),
            context=ProcedureStartContext(assets={asset.id: asset}),
            now=_NOW,
        )
    assert exc.value.asset_ids == [asset.id]


@pytest.mark.unit
def test_decide_lists_decommissioned_assets_sorted() -> None:
    asset_a = _asset(
        asset_id=UUID("00000000-0000-0000-0000-00000000000a"),
        lifecycle=AssetLifecycle.DECOMMISSIONED,
    )
    asset_b = _asset(
        asset_id=UUID("00000000-0000-0000-0000-00000000000b"),
        lifecycle=AssetLifecycle.DECOMMISSIONED,
    )
    asset_active = _asset()
    proc = _procedure(target_asset_ids=frozenset({asset_a.id, asset_b.id, asset_active.id}))
    with pytest.raises(ProcedurePlanAssetDecommissionedError) as exc:
        start_procedure.decide(
            state=proc,
            command=StartProcedure(procedure_id=proc.id),
            context=ProcedureStartContext(
                assets={asset_a.id: asset_a, asset_b.id: asset_b, asset_active.id: asset_active}
            ),
            now=_NOW,
        )
    assert exc.value.asset_ids == [asset_a.id, asset_b.id]


@pytest.mark.unit
def test_decide_is_pure_same_inputs_same_outputs() -> None:
    proc = _procedure()
    cmd = StartProcedure(procedure_id=proc.id)
    ctx = ProcedureStartContext(assets={})
    first = start_procedure.decide(state=proc, command=cmd, context=ctx, now=_NOW)
    second = start_procedure.decide(state=proc, command=cmd, context=ctx, now=_NOW)
    assert first == second

"""Property-based tests for `start_procedure.decide` (Operation BC).

Complements the example-based `test_start_procedure_decider.py` (and
its supply / enclosure gate siblings) with universal claims across
generated inputs. `start_procedure` is a gated cross-aggregate
transition (`Defined -> Running`) returning a list of
`ProcedureStarted`. The full supply / enclosure gate matrix is pinned
by the example tests; the PBT asserts the universal claims that hold
across the whole input space:

  - A None state always raises `ProcedureNotFoundError` carrying
    command.procedure_id, regardless of context / snapshot / clock.
  - On the happy path (Defined status, no target Assets, empty
    supply / enclosure context) the single `ProcedureStarted` carries
    the injected fields: procedure_id=state.id, occurred_at=now.
  - Any non-Defined source status always raises
    `ProcedureCannotStartError` carrying that status.
  - A Decommissioned target Asset always raises
    `ProcedurePlanAssetDecommissionedError`, regardless of status-ok
    state and clock.
  - Pure: same inputs return equal results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

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
from tests._strategies import aware_datetimes

if TYPE_CHECKING:
    from datetime import datetime

_NON_DEFINED_STATUSES = [s for s in ProcedureStatus if s is not ProcedureStatus.DEFINED]


def _procedure(
    *,
    procedure_id: UUID,
    target_asset_ids: frozenset[UUID] | None = None,
    status: ProcedureStatus = ProcedureStatus.DEFINED,
) -> Procedure:
    return Procedure(
        id=procedure_id,
        name=ProcedureName("Vessel-A bakeout"),
        kind="bakeout",
        target_asset_ids=target_asset_ids if target_asset_ids is not None else frozenset(),
        status=status,
        parent_run_id=None,
    )


def _asset(
    *,
    asset_id: UUID,
    lifecycle: AssetLifecycle = AssetLifecycle.ACTIVE,
) -> Asset:
    return Asset(
        id=asset_id,
        name=AssetName("EigerDetector"),
        tier=AssetTier.DEVICE,
        parent_id=UUID(int=1),
        lifecycle=lifecycle,
        family_ids=frozenset(),
    )


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    now=aware_datetimes(),
)
def test_start_procedure_on_none_state_always_raises_not_found(
    procedure_id: UUID,
    now: datetime,
) -> None:
    """A None state always raises ProcedureNotFoundError carrying the command id."""
    with pytest.raises(ProcedureNotFoundError) as exc:
        start_procedure.decide(
            state=None,
            command=StartProcedure(procedure_id=procedure_id),
            context=ProcedureStartContext(assets={}),
            now=now,
        )
    assert exc.value.procedure_id == procedure_id


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    now=aware_datetimes(),
)
def test_start_procedure_happy_path_emits_single_started_with_injected_fields(
    procedure_id: UUID,
    now: datetime,
) -> None:
    """The happy path emits one ProcedureStarted with state.id + occurred_at=now."""
    proc = _procedure(procedure_id=procedure_id)
    events = start_procedure.decide(
        state=proc,
        command=StartProcedure(procedure_id=proc.id),
        context=ProcedureStartContext(assets={}),
        now=now,
    )
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ProcedureStarted)
    assert event.procedure_id == proc.id
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    status=st.sampled_from(_NON_DEFINED_STATUSES),
    now=aware_datetimes(),
)
def test_start_procedure_on_non_defined_status_always_raises_cannot_start(
    procedure_id: UUID,
    status: ProcedureStatus,
    now: datetime,
) -> None:
    """Any non-Defined source status always raises ProcedureCannotStartError."""
    proc = _procedure(procedure_id=procedure_id, status=status)
    with pytest.raises(ProcedureCannotStartError) as exc:
        start_procedure.decide(
            state=proc,
            command=StartProcedure(procedure_id=proc.id),
            context=ProcedureStartContext(assets={}),
            now=now,
        )
    assert exc.value.current_status is status


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    asset_id=st.uuids(),
    now=aware_datetimes(),
)
def test_start_procedure_with_decommissioned_target_always_raises_asset_decommissioned(
    procedure_id: UUID,
    asset_id: UUID,
    now: datetime,
) -> None:
    """A Decommissioned target Asset always raises ProcedurePlanAssetDecommissionedError."""
    asset = _asset(asset_id=asset_id, lifecycle=AssetLifecycle.DECOMMISSIONED)
    proc = _procedure(procedure_id=procedure_id, target_asset_ids=frozenset({asset.id}))
    with pytest.raises(ProcedurePlanAssetDecommissionedError) as exc:
        start_procedure.decide(
            state=proc,
            command=StartProcedure(procedure_id=proc.id),
            context=ProcedureStartContext(assets={asset.id: asset}),
            now=now,
        )
    assert exc.value.asset_ids == [asset.id]


@pytest.mark.unit
@given(
    procedure_id=st.uuids(),
    now=aware_datetimes(),
)
def test_start_procedure_is_pure_same_input_same_output(
    procedure_id: UUID,
    now: datetime,
) -> None:
    """Two calls with identical args return equal results (no clock / id leakage)."""
    proc = _procedure(procedure_id=procedure_id)
    command = StartProcedure(procedure_id=proc.id)
    context = ProcedureStartContext(assets={})
    first = start_procedure.decide(state=proc, command=command, context=context, now=now)
    second = start_procedure.decide(state=proc, command=command, context=context, now=now)
    assert first == second

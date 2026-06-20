"""Tier-0 manifest recording: decide_resolved_steps_recorded + step_to_payload.

Covers:
  - the helper emits one ResolvedStepsRecorded for a Defined Procedure,
    carrying the resolved steps + count.
  - None / already-Running state -> no event (the Conductor's
    start_procedure owns the lifecycle failure; the helper stays silent so
    the conduct route keeps its failures-in-body contract).
  - step_to_payload round-trips every step kind back to an equal Step via
    the public wire path (ConductProcedureRequest validation + step_from_wire),
    proving a pinned manifest can be replayed.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.operation.aggregates.procedure import (
    ProcedureRegistered,
    ProcedureStarted,
    ResolvedStepsRecorded,
    fold,
)
from cora.operation.conductor import (
    ActionStep,
    CheckStep,
    EqualsCriterion,
    SetpointStep,
    Step,
    WithinToleranceCriterion,
    step_to_payload,
)
from cora.operation.features.conduct_procedure.manifest import (
    decide_resolved_steps_recorded,
)
from cora.operation.features.conduct_procedure.route import (
    ConductProcedureRequest,
    step_from_wire,
)

_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)


def _registered() -> tuple[UUID, ProcedureRegistered]:
    procedure_id = uuid4()
    return procedure_id, ProcedureRegistered(
        procedure_id=procedure_id,
        name="alignment",
        kind="alignment",
        target_asset_ids=(),
        parent_run_id=None,
        occurred_at=_NOW,
    )


@pytest.mark.unit
def test_decide_records_manifest_for_defined_procedure() -> None:
    procedure_id, registered = _registered()
    state = fold([registered])
    steps = (
        {"kind": "setpoint", "address": "2bma:rot", "value": 1.0, "verify": False},
        {"kind": "action", "name": "collect", "params": {"dwell": 0.1}},
    )

    events = decide_resolved_steps_recorded(state, steps, now=_NOW)

    assert len(events) == 1
    event = events[0]
    assert isinstance(event, ResolvedStepsRecorded)
    assert event.procedure_id == procedure_id
    assert event.resolved_steps == steps
    assert event.step_count == 2
    assert event.occurred_at == _NOW


@pytest.mark.unit
def test_decide_records_nothing_when_state_is_none() -> None:
    steps = ({"kind": "setpoint", "address": "a", "value": 1.0, "verify": False},)
    assert decide_resolved_steps_recorded(None, steps, now=_NOW) == []


@pytest.mark.unit
def test_decide_records_nothing_when_procedure_already_running() -> None:
    procedure_id, registered = _registered()
    running = fold([registered, ProcedureStarted(procedure_id=procedure_id, occurred_at=_NOW)])
    steps = ({"kind": "setpoint", "address": "a", "value": 1.0, "verify": False},)
    assert decide_resolved_steps_recorded(running, steps, now=_NOW) == []


@pytest.mark.unit
@pytest.mark.parametrize(
    "step",
    [
        SetpointStep(address="2bma:rot", value=12.5, verify=True),
        SetpointStep(address="2bma:energy", value=(1, 2, 3)),
        ActionStep(name="collect", params={"dwell": 0.1, "detector": "2bma:cam1"}),
        CheckStep(address="2bma:shutter", criterion=EqualsCriterion(expected="Open")),
        CheckStep(
            address="2bma:temp",
            criterion=WithinToleranceCriterion(expected=100.0, tolerance=0.5),
        ),
    ],
)
def test_step_to_payload_round_trips_through_step_from_wire(step: Step) -> None:
    payload = step_to_payload(step)
    request = ConductProcedureRequest.model_validate({"steps": [payload]})
    rebuilt = step_from_wire(request.steps[0])
    assert rebuilt == step

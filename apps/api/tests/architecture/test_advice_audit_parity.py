"""G3: the advice provenance has a parity home on BOTH recording targets.

`advice_to_audit_fields` is the single producer of the decision-provenance
subset of a `SteeringAdvice`. Its four validated fields {reasoning,
confidence, confidence_source, alternatives} must land verbatim on the
in-Run iteration ledger (`ProcedureIterationEnded`) AND on the across-Run
Decision record (`DecisionRegistered`), so the two recording homes capture
the same audit facts and cannot drift.

`model_ref` is the honest exception (the G3 downgrade): it lands on the
in-Run event under its mapper name (`model_ref`) but is convention-only on
the Decision side, where it rides `DecisionRegistered.inputs` rather than a
typed field. This test pins that asymmetry so it stays a deliberate,
documented choice rather than silent drift, until a typed model_ref validator
is earned.
"""

import dataclasses

import pytest

from cora.decision.aggregates.decision import DecisionRegistered
from cora.operation.aggregates.procedure import ProcedureIterationEnded
from cora.operation.ports.decide_port import AdviceAuditFields

_AUDIT = {f.name for f in dataclasses.fields(AdviceAuditFields)}
_ITERATION = {f.name for f in dataclasses.fields(ProcedureIterationEnded)}
_DECISION = {f.name for f in dataclasses.fields(DecisionRegistered)}
_FOUR_VALIDATED = {"reasoning", "confidence", "confidence_source", "alternatives"}


@pytest.mark.architecture
def test_advice_audit_fields_shape_is_pinned() -> None:
    """The mapper's output is exactly the four validated fields plus model_ref."""
    assert _FOUR_VALIDATED | {"model_ref"} == _AUDIT


@pytest.mark.architecture
def test_four_validated_fields_have_a_home_on_both_recording_targets() -> None:
    """In-Run ledger and across-Run Decision both carry the four audit fields."""
    assert _FOUR_VALIDATED <= _ITERATION, f"in-Run ledger missing {_FOUR_VALIDATED - _ITERATION}"
    assert _FOUR_VALIDATED <= _DECISION, f"Decision record missing {_FOUR_VALIDATED - _DECISION}"


@pytest.mark.architecture
def test_model_ref_has_in_run_home_but_is_convention_only_on_decision() -> None:
    """model_ref lands in-Run under its mapper name but rides Decision.inputs."""
    assert "model_ref" in _ITERATION
    assert "model_ref" not in _DECISION
    assert "inputs" in _DECISION


@pytest.mark.architecture
def test_advised_stop_verdict_slot_exists_on_iteration_ledger() -> None:
    """The steering verdict has its own slot, kept distinct from converged."""
    assert "advised_stop" in _ITERATION
    assert "converged" in _ITERATION

"""Translation from an Agent's declared brain to the LLM port's model shape.

The seam matters more than it looks. Both debrief call sites once built their
request from a module-level default, so the Agent's declaration was inert and
the catalog gate at `define_agent` governed nothing about the call. Reading
the legacy `model_ref` slot would put that back, differently: the slot is
empty for every Agent defined since the seeds moved to `brain`.
"""

import pytest

from cora.agent._model_ref import to_port_model_ref
from cora.agent.aggregates.agent import (
    BrainRef,
    InvalidAgentBrainKindError,
    ModelRef,
)


@pytest.mark.unit
def test_language_model_brain_carries_every_field_to_the_port() -> None:
    brain = BrainRef.for_model(
        ModelRef(provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001")
    )

    port_ref = to_port_model_ref(brain)

    assert port_ref.provider == "anthropic"
    assert port_ref.model == "claude-sonnet-4-6"
    assert port_ref.snapshot_pin == "20251001"


@pytest.mark.unit
def test_rule_brain_refuses_rather_than_serving_a_model_it_does_not_have() -> None:
    with pytest.raises(InvalidAgentBrainKindError) as excinfo:
        to_port_model_ref(BrainRef.for_rule("ProcedureWatcher:v1"))

    assert excinfo.value.kind == "Rule"


@pytest.mark.unit
def test_absent_brain_refuses() -> None:
    """State without a brain is unreachable through the evolver, so a caller
    holding one built an Agent by hand. Refusing keeps the seam's guarantee
    from depending on how the Agent was constructed."""
    with pytest.raises(InvalidAgentBrainKindError) as excinfo:
        to_port_model_ref(None)

    assert excinfo.value.kind is None

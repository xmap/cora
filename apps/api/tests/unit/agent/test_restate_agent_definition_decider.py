"""Decider tests for `restate_agent_definition`.

Events are INSERT-only, so a stream written before `brain` existed cannot be
rewritten to carry one. This slice appends the correction instead, which is
what lets `brain_from_legacy_model_ref` and `Agent.model_ref` eventually be
removed rather than kept forever.

The same event serves the rename: supply `name` and omit `brain`.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    Agent,
    AgentCannotRestateDefinitionError,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    BrainRef,
    InvalidAgentDefinitionRestatementError,
    InvalidAgentRestatementReasonError,
    ModelRef,
)
from cora.agent.features.restate_agent_definition.command import RestateAgentDefinition
from cora.agent.features.restate_agent_definition.decider import decide

_NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)
_AGENT_ID = uuid4()
_LEGACY_SENTINEL = ModelRef(provider="deterministic", model="agent:ProcedureWatcher:v1")


def _agent(
    *,
    status: AgentStatus = AgentStatus.VERSIONED,
    name: str = "Procedure Watcher",
    brain: BrainRef | None = None,
) -> Agent:
    return Agent(
        id=_AGENT_ID,
        kind=AgentKind("ProcedureWatcher"),
        name=AgentName(name),
        version=AgentVersion("1.0.0"),
        model_ref=_LEGACY_SENTINEL,
        brain=brain if brain is not None else BrainRef.for_rule("ProcedureWatcher:v1"),
        status=status,
    )


def _command(**overrides: object) -> RestateAgentDefinition:
    base: dict[str, object] = {"agent_id": _AGENT_ID, "reason": "brain restated post-migration"}
    base.update(overrides)
    return RestateAgentDefinition(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_restating_a_brain_emits_the_event() -> None:
    events = decide(_agent(), _command(brain=BrainRef.for_rule("ProcedureWatcher:v2")), now=_NOW)

    assert len(events) == 1
    assert events[0].brain == BrainRef.for_rule("ProcedureWatcher:v2")
    assert events[0].name is None
    assert events[0].reason == "brain restated post-migration"


@pytest.mark.unit
def test_restating_only_a_name_leaves_the_brain_unnamed() -> None:
    """The rename case slice 4 reuses: name supplied, brain untouched."""
    events = decide(_agent(), _command(name="Campaign Coordinator"), now=_NOW)

    assert len(events) == 1
    assert events[0].name == "Campaign Coordinator"
    assert events[0].brain is None


@pytest.mark.unit
def test_restating_neither_is_refused() -> None:
    """An event restating nothing is a governance write with no content."""
    with pytest.raises(InvalidAgentDefinitionRestatementError):
        decide(_agent(), _command(), now=_NOW)


@pytest.mark.unit
def test_a_deprecated_agent_cannot_be_restated() -> None:
    with pytest.raises(AgentCannotRestateDefinitionError):
        decide(
            _agent(status=AgentStatus.DEPRECATED),
            _command(name="Too Late"),
            now=_NOW,
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    "status", [AgentStatus.DEFINED, AgentStatus.VERSIONED, AgentStatus.SUSPENDED]
)
def test_every_non_terminal_status_may_be_restated(status: AgentStatus) -> None:
    events = decide(_agent(status=status), _command(name="Renamed"), now=_NOW)

    assert len(events) == 1


@pytest.mark.unit
def test_missing_agent_is_refused() -> None:
    with pytest.raises(AgentNotFoundError):
        decide(None, _command(name="Ghost"), now=_NOW)


@pytest.mark.unit
def test_restating_every_supplied_field_to_its_current_value_is_a_no_op() -> None:
    events = decide(
        _agent(),
        _command(name="Procedure Watcher", brain=BrainRef.for_rule("ProcedureWatcher:v1")),
        now=_NOW,
    )

    assert events == []


@pytest.mark.unit
def test_idempotence_is_judged_on_the_supplied_fields_only() -> None:
    """A command naming just the brain must not be called unchanged because
    the name it never mentioned still matches.

    Judging a partial restatement against a field the caller said nothing
    about would silently drop the change they did ask for.
    """
    events = decide(_agent(), _command(brain=BrainRef.for_rule("ProcedureWatcher:v9")), now=_NOW)

    assert len(events) == 1
    assert events[0].brain == BrainRef.for_rule("ProcedureWatcher:v9")


@pytest.mark.unit
def test_a_whitespace_only_reason_is_refused() -> None:
    with pytest.raises(InvalidAgentRestatementReasonError):
        decide(_agent(), _command(name="Renamed", reason="   "), now=_NOW)


@pytest.mark.unit
def test_the_name_goes_through_the_same_vo_the_genesis_used() -> None:
    """A restatement must not be able to introduce a name `define_agent`
    would have refused."""
    from cora.agent.aggregates.agent import InvalidAgentNameError

    with pytest.raises(InvalidAgentNameError):
        decide(_agent(), _command(name="   "), now=_NOW)


@pytest.mark.unit
def test_the_legacy_model_ref_is_left_exactly_as_the_genesis_wrote_it() -> None:
    """Restatement makes an Agent stop DEPENDING on the legacy slot; it does
    not rewrite what that Agent originally said. The record stays faithful."""
    from cora.agent.aggregates.agent.evolver import evolve

    prior = _agent()
    event = decide(prior, _command(brain=BrainRef.for_rule("ProcedureWatcher:v2")), now=_NOW)[0]

    after = evolve(prior, event)

    assert after.model_ref == _LEGACY_SENTINEL
    assert after.brain == BrainRef.for_rule("ProcedureWatcher:v2")

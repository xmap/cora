"""Pure-decider tests for the `define_agent` slice."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent import (
    AGENT_CAPABILITIES_MAX_COUNT,
    AgentCanonicalUri,
    AgentCapability,
    AgentDefined,
    AgentKind,
    AgentName,
    AgentStatus,
    AgentVersion,
    InvalidAgentCanonicalUriError,
    InvalidAgentCapabilitiesError,
    InvalidAgentCapabilityError,
    InvalidAgentDescriptionError,
    InvalidAgentKindError,
    InvalidAgentNameError,
    InvalidAgentVersionError,
    ModelRef,
)
from cora.agent.aggregates.agent.state import (
    Agent,
    AgentAlreadyExistsError,
    AgentBrainUnspecifiedError,
    BrainRef,
)
from cora.agent.features.define_agent.command import DefineAgent
from cora.agent.features.define_agent.decider import decide

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)
_NEW_ID = uuid4()
_MODEL = ModelRef(provider="anthropic", model="claude-sonnet-4-6")


def _command(**overrides: object) -> DefineAgent:
    base: dict[str, object] = {
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": _MODEL,
    }
    base.update(overrides)
    return DefineAgent(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_command_naming_neither_brain_nor_model_ref_is_refused() -> None:
    """An Agent that names nothing to think with produces an `AgentDefined`
    the evolver refuses to fold, so it is caught at write time rather than
    discovered at replay.

    The wire rejects this first, so reaching the decider means an in-process
    caller. The invariant lives with the aggregate rather than with one of
    its two front doors, or a third front door would arrive without it.
    """
    with pytest.raises(AgentBrainUnspecifiedError):
        decide(None, _command(model_ref=None), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_a_rule_brained_command_needs_no_model_ref() -> None:
    """The whole point of the slice: defining a rule-brained Agent without
    inventing a language model it will never call."""
    events = decide(
        None,
        _command(model_ref=None, brain=BrainRef.for_rule("ExperimentSteerer:v1")),
        now=_NOW,
        new_id=_NEW_ID,
    )

    assert len(events) == 1
    assert events[0].model_ref is None
    assert events[0].brain == BrainRef.for_rule("ExperimentSteerer:v1")


@pytest.mark.unit
def test_minimal_command_emits_single_agent_defined() -> None:
    events = decide(state=None, command=_command(), now=_NOW, new_id=_NEW_ID)
    assert len(events) == 1
    assert isinstance(events[0], AgentDefined)
    e = events[0]
    assert e.agent_id == _NEW_ID
    assert e.kind == "RunDebriefer"
    assert e.name == "Run Debrief"
    assert e.version == "v1"
    assert e.model_ref == _MODEL
    assert e.description is None
    assert e.canonical_uri is None
    assert e.prompt_template_id is None
    assert e.capabilities == frozenset()
    assert e.occurred_at == _NOW


@pytest.mark.unit
def test_full_command_carries_all_optional_fields() -> None:
    template_id = uuid4()
    events = decide(
        state=None,
        command=_command(
            description="Synthesises terminal Runs.",
            canonical_uri="https://example.org/agents/run-debrief",
            prompt_template_id=template_id,
            capabilities=frozenset({"summarize", "categorize"}),
        ),
        now=_NOW,
        new_id=_NEW_ID,
    )
    e = events[0]
    assert e.description == "Synthesises terminal Runs."
    assert e.canonical_uri == "https://example.org/agents/run-debrief"
    assert e.prompt_template_id == template_id
    assert e.capabilities == frozenset({"summarize", "categorize"})


@pytest.mark.unit
def test_genesis_collision_raises_already_exists() -> None:
    existing = Agent(
        id=_NEW_ID,
        kind=AgentKind("RunDebriefer"),
        name=AgentName("Run Debrief"),
        version=AgentVersion("v1"),
        model_ref=_MODEL,
    )
    assert existing.status is AgentStatus.DEFINED
    with pytest.raises(AgentAlreadyExistsError):
        decide(state=existing, command=_command(), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_kind_raises() -> None:
    with pytest.raises(InvalidAgentKindError):
        decide(state=None, command=_command(kind=""), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_name_raises() -> None:
    with pytest.raises(InvalidAgentNameError):
        decide(state=None, command=_command(name=""), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_version_raises() -> None:
    with pytest.raises(InvalidAgentVersionError):
        decide(state=None, command=_command(version=""), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_description_raises() -> None:
    with pytest.raises(InvalidAgentDescriptionError):
        decide(state=None, command=_command(description=""), now=_NOW, new_id=_NEW_ID)


@pytest.mark.unit
def test_invalid_canonical_uri_raises() -> None:
    with pytest.raises(InvalidAgentCanonicalUriError):
        decide(
            state=None,
            command=_command(canonical_uri="http://no-https.example.org"),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_invalid_capability_raises() -> None:
    with pytest.raises(InvalidAgentCapabilityError):
        decide(
            state=None,
            command=_command(capabilities=frozenset({""})),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_over_cap_capabilities_raises() -> None:
    with pytest.raises(InvalidAgentCapabilitiesError):
        decide(
            state=None,
            command=_command(
                capabilities=frozenset(f"cap-{i}" for i in range(AGENT_CAPABILITIES_MAX_COUNT + 1))
            ),
            now=_NOW,
            new_id=_NEW_ID,
        )


@pytest.mark.unit
def test_capabilities_round_trip_through_vo() -> None:
    """VOs trim individual capability entries; the decider preserves trimmed values."""
    events = decide(
        state=None,
        command=_command(capabilities=frozenset({"  summarize  ", "  categorize  "})),
        now=_NOW,
        new_id=_NEW_ID,
    )
    e = events[0]
    assert e.capabilities == frozenset({"summarize", "categorize"})


@pytest.mark.unit
def test_event_uses_handler_supplied_now_and_new_id() -> None:
    """Non-determinism principle: decider takes now + new_id as inputs."""
    custom_now = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)
    custom_id = uuid4()
    events = decide(state=None, command=_command(), now=custom_now, new_id=custom_id)
    assert events[0].occurred_at == custom_now
    assert events[0].agent_id == custom_id


@pytest.mark.unit
def test_canonical_uri_value_object_trim_propagates() -> None:
    """`AgentCanonicalUri(...)` trims; the decider passes the trimmed value."""
    events = decide(
        state=None,
        command=_command(canonical_uri="  https://example.org/agent  "),
        now=_NOW,
        new_id=_NEW_ID,
    )
    assert events[0].canonical_uri == "https://example.org/agent"
    # And construction of an `AgentCanonicalUri` from the wire would round-trip.
    assert AgentCanonicalUri(events[0].canonical_uri).value == "https://example.org/agent"


@pytest.mark.unit
def test_decider_does_not_emit_actor_registered() -> None:
    """The Access BC co-write is built by the HANDLER, not this decider.

    Decider must stay focused on Agent BC concerns; the cross-BC
    `ActorRegistered` event is the handler's responsibility.
    """
    events = decide(state=None, command=_command(), now=_NOW, new_id=_NEW_ID)
    assert all(isinstance(e, AgentDefined) for e in events)


@pytest.mark.unit
def test_capability_value_object_normalisation() -> None:
    """Make sure individual capability VO construction works as expected."""
    cap = AgentCapability("  summarize  ")
    assert cap.value == "summarize"

"""Property-based tests for `define_agent.decide` (Agent BC).

Complements the example-based `test_define_agent_decider.py` with
universal claims across generated inputs. The genesis decider is pure

    (state, command, *, now, new_id) -> list[AgentDefined]

Load-bearing properties:

  - Any non-None state always raises `AgentAlreadyExistsError` carrying
    state.id (idempotency-as-error), regardless of command.
  - Capability cardinality over AGENT_CAPABILITIES_MAX_COUNT always
    raises `InvalidAgentCapabilitiesError` carrying the offending count.
  - On the happy path the single `AgentDefined` carries the
    injected/passthrough fields: agent_id=new_id, kind, name, version,
    model_ref, occurred_at=now.
  - Pure: same inputs return equal events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.agent.aggregates.agent import (
    AGENT_CAPABILITIES_MAX_COUNT,
    AgentCapability,
    AgentDefined,
    AgentKind,
    AgentName,
    AgentVersion,
    InvalidAgentCapabilitiesError,
    ModelRef,
)
from cora.agent.aggregates.agent.state import (
    Agent,
    AgentAlreadyExistsError,
)
from cora.agent.features.define_agent.command import DefineAgent
from cora.agent.features.define_agent.decider import decide
from tests._strategies import aware_datetimes, printable_ascii_text

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID

_KIND = "RunDebriefer"
_NAME = "Run Debrief"
_VERSION = "v1"
_MODEL = ModelRef(provider="anthropic", model="claude-sonnet-4-6")
_CAPABILITIES = frozenset({"summarize", "categorize"})


def _command(**overrides: object) -> DefineAgent:
    base: dict[str, object] = {
        "kind": _KIND,
        "name": _NAME,
        "version": _VERSION,
        "model_ref": _MODEL,
    }
    base.update(overrides)
    return DefineAgent(**base)  # type: ignore[arg-type]


def _state(*, agent_id: UUID) -> Agent:
    return Agent(
        id=agent_id,
        kind=AgentKind(_KIND),
        name=AgentName(_NAME),
        version=AgentVersion(_VERSION),
        model_ref=_MODEL,
    )


@pytest.mark.unit
@given(
    existing_id=st.uuids(),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_existing_state_always_raises_already_exists(
    existing_id: UUID,
    now: datetime,
    new_id: UUID,
) -> None:
    """Any non-None state raises AgentAlreadyExistsError carrying state.id."""
    existing = _state(agent_id=existing_id)
    with pytest.raises(AgentAlreadyExistsError) as exc:
        decide(state=existing, command=_command(), now=now, new_id=new_id)
    assert exc.value.agent_id == existing_id


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    new_id=st.uuids(),
    count=st.integers(min_value=AGENT_CAPABILITIES_MAX_COUNT + 1, max_value=64),
)
def test_define_over_cap_capabilities_always_raises_invalid_capabilities(
    now: datetime,
    new_id: UUID,
    count: int,
) -> None:
    """Capability count over the cap raises InvalidAgentCapabilitiesError."""
    capabilities = frozenset(f"cap-{i}" for i in range(count))
    with pytest.raises(InvalidAgentCapabilitiesError):
        decide(
            state=None,
            command=_command(capabilities=capabilities),
            now=now,
            new_id=new_id,
        )


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_on_empty_stream_emits_single_event_with_injected_fields(
    now: datetime,
    new_id: UUID,
) -> None:
    """Empty stream emits one AgentDefined carrying the injected fields."""
    events = decide(state=None, command=_command(), now=now, new_id=new_id)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, AgentDefined)
    assert event.agent_id == new_id
    assert event.kind == _KIND
    assert event.name == _NAME
    assert event.version == _VERSION
    assert event.model_ref == _MODEL
    assert event.occurred_at == now


@pytest.mark.unit
@given(
    description=printable_ascii_text(min_size=1, max_size=200),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_threads_optional_fields_into_event(
    description: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Optional command fields are threaded through onto the event."""
    events = decide(
        state=None,
        command=_command(description=description, capabilities=_CAPABILITIES),
        now=now,
        new_id=new_id,
    )
    event = events[0]
    assert event.description == description
    assert event.capabilities == _CAPABILITIES


@pytest.mark.unit
@given(
    cap=printable_ascii_text(min_size=1, max_size=100),
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_preserves_capability_value_object_normalisation(
    cap: str,
    now: datetime,
    new_id: UUID,
) -> None:
    """Per-entry capabilities round-trip through the AgentCapability VO."""
    events = decide(
        state=None,
        command=_command(capabilities=frozenset({cap})),
        now=now,
        new_id=new_id,
    )
    assert events[0].capabilities == frozenset({AgentCapability(cap).value})


@pytest.mark.unit
@given(
    now=aware_datetimes(),
    new_id=st.uuids(),
)
def test_define_is_pure_same_input_same_output(
    now: datetime,
    new_id: UUID,
) -> None:
    """Two calls with identical args return equal events (no clock/id leakage)."""
    command = _command(capabilities=_CAPABILITIES)
    first = decide(state=None, command=command, now=now, new_id=new_id)
    second = decide(state=None, command=command, now=now, new_id=new_id)
    assert first == second

"""Event (de)serialization round-trip tests for the Agent aggregate."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.agent.aggregates.agent.events import (
    AgentBudgetUpdated,
    AgentDefined,
    AgentDeprecated,
    AgentResumed,
    AgentSuspended,
    AgentToolGranted,
    AgentToolRevoked,
    AgentVersioned,
    deserialize_model_ref,
    event_type_name,
    from_stored,
    serialize_model_ref,
    to_payload,
)
from cora.agent.aggregates.agent.state import ModelRef
from cora.infrastructure.ports.event_store import StoredEvent
from cora.shared.identity import ActorId

_NOW = datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)


def _stored(
    event_type: str,
    payload: dict[str, object],
) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Agent",
        stream_id=uuid4(),
        version=1,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


# ---------- ModelRef serialize / deserialize ----------


@pytest.mark.unit
def test_serialize_model_ref_full_triple() -> None:
    m = ModelRef(provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001")
    assert serialize_model_ref(m) == {
        "provider": "anthropic",
        "model": "claude-sonnet-4-6",
        "snapshot_pin": "20251001",
    }


@pytest.mark.unit
def test_serialize_model_ref_null_snapshot_pin() -> None:
    m = ModelRef(provider="openai", model="o4-mini", snapshot_pin=None)
    assert serialize_model_ref(m) == {
        "provider": "openai",
        "model": "o4-mini",
        "snapshot_pin": None,
    }


@pytest.mark.unit
def test_deserialize_model_ref_round_trips() -> None:
    original = ModelRef(provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001")
    payload = serialize_model_ref(original)
    assert deserialize_model_ref(payload) == original


@pytest.mark.unit
def test_deserialize_model_ref_raises_on_missing_field() -> None:
    with pytest.raises(ValueError, match="Malformed ModelRef payload"):
        deserialize_model_ref({"provider": "anthropic"})  # missing 'model'


# ---------- event_type_name ----------


@pytest.mark.unit
def test_event_type_name_returns_class_name() -> None:
    e = AgentDefined(
        agent_id=uuid4(),
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_NOW,
    )
    assert event_type_name(e) == "AgentDefined"


# ---------- AgentDefined serialize / deserialize ----------


@pytest.mark.unit
def test_to_payload_serializes_agent_defined_minimal() -> None:
    agent_id = uuid4()
    e = AgentDefined(
        agent_id=agent_id,
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_NOW,
    )
    payload = to_payload(e)
    assert payload == {
        "agent_id": str(agent_id),
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
        "description": None,
        "canonical_uri": None,
        "prompt_template_id": None,
        "capabilities": [],
        "occurred_at": _NOW.isoformat(),
        # on a minimal define (operators add tools / budget via separate
        # commands post-genesis).
        "tools": [],
        "monthly_usd_cap": None,
        "daily_token_cap": None,
    }


@pytest.mark.unit
def test_to_payload_serializes_agent_defined_full() -> None:
    agent_id = uuid4()
    template_id = uuid4()
    e = AgentDefined(
        agent_id=agent_id,
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(
            provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001"
        ),
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=template_id,
        capabilities=frozenset({"summarize", "categorize"}),
        occurred_at=_NOW,
    )
    payload = to_payload(e)
    assert payload["prompt_template_id"] == str(template_id)
    assert payload["capabilities"] == ["categorize", "summarize"]  # sorted for determinism
    assert payload["model_ref"]["snapshot_pin"] == "20251001"


@pytest.mark.unit
def test_round_trip_agent_defined_full() -> None:
    agent_id = uuid4()
    template_id = uuid4()
    original = AgentDefined(
        agent_id=agent_id,
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(
            provider="anthropic", model="claude-sonnet-4-6", snapshot_pin="20251001"
        ),
        description="Synthesises terminal Runs.",
        canonical_uri="https://example.org/agents/run-debrief",
        prompt_template_id=template_id,
        capabilities=frozenset({"summarize", "categorize"}),
        occurred_at=_NOW,
    )
    stored = _stored("AgentDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_round_trip_agent_defined_minimal() -> None:
    original = AgentDefined(
        agent_id=uuid4(),
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_NOW,
    )
    stored = _stored("AgentDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_from_stored_agent_defined_raises_on_missing_field() -> None:
    stored = _stored(
        "AgentDefined",
        {"agent_id": str(uuid4())},  # missing kind / name / etc.
    )
    with pytest.raises(ValueError, match="Malformed AgentDefined payload"):
        from_stored(stored)


# ---------- AgentVersioned ----------


@pytest.mark.unit
def test_to_payload_serializes_agent_versioned() -> None:
    agent_id = uuid4()
    e = AgentVersioned(agent_id=agent_id, version="v1", occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "version": "v1",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_versioned() -> None:
    original = AgentVersioned(agent_id=uuid4(), version="v1", occurred_at=_NOW)
    stored = _stored("AgentVersioned", to_payload(original))
    assert from_stored(stored) == original


# ---------- AgentDeprecated ----------


@pytest.mark.unit
def test_to_payload_serializes_agent_deprecated_with_reason() -> None:
    agent_id = uuid4()
    e = AgentDeprecated(agent_id=agent_id, reason="model retired", occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "reason": "model retired",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_to_payload_serializes_agent_deprecated_without_reason() -> None:
    agent_id = uuid4()
    e = AgentDeprecated(agent_id=agent_id, reason=None, occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "reason": None,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_deprecated() -> None:
    original = AgentDeprecated(agent_id=uuid4(), reason="model retired", occurred_at=_NOW)
    stored = _stored("AgentDeprecated", to_payload(original))
    assert from_stored(stored) == original


# ---------- lifecycle widening: Suspended / Resumed / ToolGrant / Budget ----------


@pytest.mark.unit
def test_to_payload_serializes_agent_suspended() -> None:
    agent_id = uuid4()
    suspended_by = ActorId(uuid4())
    e = AgentSuspended(
        agent_id=agent_id,
        reason="cost overrun",
        suspended_by=suspended_by,
        occurred_at=_NOW,
    )
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "reason": "cost overrun",
        "suspended_by": str(suspended_by),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_suspended() -> None:
    original = AgentSuspended(
        agent_id=uuid4(),
        reason="x",
        suspended_by=ActorId(uuid4()),
        occurred_at=_NOW,
    )
    stored = _stored("AgentSuspended", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_agent_resumed() -> None:
    agent_id = uuid4()
    resumed_by = ActorId(uuid4())
    e = AgentResumed(agent_id=agent_id, resumed_by=resumed_by, occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "resumed_by": str(resumed_by),
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_resumed() -> None:
    original = AgentResumed(
        agent_id=uuid4(),
        resumed_by=ActorId(uuid4()),
        occurred_at=_NOW,
    )
    stored = _stored("AgentResumed", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_agent_tool_granted() -> None:
    agent_id = uuid4()
    e = AgentToolGranted(agent_id=agent_id, tool_name="read_run", occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "tool_name": "read_run",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_tool_granted() -> None:
    original = AgentToolGranted(agent_id=uuid4(), tool_name="read_run", occurred_at=_NOW)
    stored = _stored("AgentToolGranted", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_agent_tool_revoked() -> None:
    agent_id = uuid4()
    e = AgentToolRevoked(agent_id=agent_id, tool_name="read_run", occurred_at=_NOW)
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "tool_name": "read_run",
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_tool_revoked() -> None:
    original = AgentToolRevoked(agent_id=uuid4(), tool_name="read_run", occurred_at=_NOW)
    stored = _stored("AgentToolRevoked", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_to_payload_serializes_agent_budget_updated_both_caps() -> None:
    agent_id = uuid4()
    e = AgentBudgetUpdated(
        agent_id=agent_id,
        monthly_usd_cap=100.0,
        daily_token_cap=500_000,
        occurred_at=_NOW,
    )
    assert to_payload(e) == {
        "agent_id": str(agent_id),
        "monthly_usd_cap": 100.0,
        "daily_token_cap": 500_000,
        "occurred_at": _NOW.isoformat(),
    }


@pytest.mark.unit
def test_round_trip_agent_budget_updated_with_null_caps() -> None:
    original = AgentBudgetUpdated(
        agent_id=uuid4(), monthly_usd_cap=None, daily_token_cap=None, occurred_at=_NOW
    )
    stored = _stored("AgentBudgetUpdated", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_agent_defined_round_trip_with_tools_and_budget_caps() -> None:
    """Iter 2 payload fields round-trip even when set non-default."""
    original = AgentDefined(
        agent_id=uuid4(),
        kind="RunDebriefer",
        name="Run Debrief",
        version="v1",
        model_ref=ModelRef(provider="anthropic", model="claude-sonnet-4-6"),
        description=None,
        canonical_uri=None,
        prompt_template_id=None,
        capabilities=frozenset(),
        occurred_at=_NOW,
        tools=frozenset({"read_run", "read_dataset"}),
        monthly_usd_cap=200.0,
        daily_token_cap=2_000_000,
    )
    stored = _stored("AgentDefined", to_payload(original))
    assert from_stored(stored) == original


@pytest.mark.unit
def test_agent_defined_from_stored_tolerates_pre_iter2_payload() -> None:
    """Pre-iter-2 streams have no tools / budget keys; from_stored must default."""
    agent_id = uuid4()
    pre_iter2_payload: dict[str, object] = {
        "agent_id": str(agent_id),
        "kind": "RunDebriefer",
        "name": "Run Debrief",
        "version": "v1",
        "model_ref": {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "snapshot_pin": None,
        },
        "description": None,
        "canonical_uri": None,
        "prompt_template_id": None,
        "capabilities": [],
        "occurred_at": _NOW.isoformat(),
        # tools / budget fields absent
    }
    rebuilt = from_stored(_stored("AgentDefined", pre_iter2_payload))
    assert isinstance(rebuilt, AgentDefined)
    assert rebuilt.tools == frozenset()
    assert rebuilt.monthly_usd_cap is None
    assert rebuilt.daily_token_cap is None


# ---------- Foreign event_type fails loud ----------


@pytest.mark.unit
def test_from_stored_raises_on_unknown_event_type() -> None:
    stored = _stored("SomethingElse", {})
    with pytest.raises(ValueError, match="Unknown AgentEvent event_type"):
        from_stored(stored)


# ---------------------------------------------------------------------------
# Malformed-payload defensive arms (every event type's `try/except` raise)
#
# `from_stored` wraps each event-type's constructor in
# `try: ... except (KeyError, TypeError, AttributeError): raise ValueError`.
# This is the schema-drift insurance for a corrupted event row (older
# producer's payload shape diverged from the current evolver's expectations).
# `AgentDefined` is already pinned above; this parametrized test closes the
# remaining 7 event types so a future field addition can't silently break
# replay on legacy events without surfacing here.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(
    "event_type",
    [
        "AgentVersioned",
        "AgentDeprecated",
        "AgentSuspended",
        "AgentResumed",
        "AgentToolGranted",
        "AgentToolRevoked",
        "AgentBudgetUpdated",
    ],
)
def test_from_stored_raises_on_malformed_payload(event_type: str) -> None:
    """An empty payload triggers KeyError on the first required field
    lookup; the wrapping `except` surfaces a ValueError tagged with the
    event_type so operators can grep the failure back to the bad row."""
    stored = _stored(event_type, {})
    with pytest.raises(ValueError, match=f"Malformed {event_type} payload"):
        from_stored(stored)

"""Unit tests for tier-1 (`events`) redaction.

Uses `AgentDefined`'s real, generated disposition entry (not a
hand-tuned test-only one) for the payload-shape tests, so "a bare str
drops with nobody editing a list" is demonstrated against the actual
committed table.
"""

from uuid import uuid4

import pytest

from cora.infrastructure.record_export import TokenMap, UnknownEventTypeError, redact_tier1_payload
from cora.infrastructure.record_export._redact_tier1 import Tier1Redactor

_AGENT_ID = "01900000-0000-7000-8000-0000000000c1"
_PROMPT_TEMPLATE_ID = "01900000-0000-7000-8000-0000000000c2"


def _agent_defined_payload() -> dict[str, object]:
    return {
        "agent_id": _AGENT_ID,
        "canonical_uri": "https://internal/agents/foo",
        "capabilities": "read,write",
        "daily_token_cap": 1000,
        "description": "an agent that does things",
        "kind": "assistant",
        "model_ref": {"model": "claude-x", "provider": "anthropic", "snapshot_pin": "2026-01-01"},
        "monthly_usd_cap": 50.0,
        "name": "Foo Agent",
        "occurred_at": "2026-05-15T12:00:00+00:00",
        "prompt_template_id": _PROMPT_TEMPLATE_ID,
        "tools": "search,browse",
        "version": "v1",
    }


def test_bare_str_drop_text_field_drops_with_no_list_edited() -> None:
    """AgentDefined.name is drop:text in the real generated table."""
    redacted = redact_tier1_payload("AgentDefined", _agent_defined_payload(), token_map=TokenMap())
    assert "name" not in redacted
    assert "canonical_uri" not in redacted
    assert "kind" not in redacted
    assert "tools" not in redacted
    assert "version" not in redacted


def test_keep_number_and_keep_time_fields_survive_unchanged() -> None:
    payload = _agent_defined_payload()
    redacted = redact_tier1_payload("AgentDefined", payload, token_map=TokenMap())
    assert redacted["daily_token_cap"] == 1000
    assert redacted["monthly_usd_cap"] == 50.0
    assert redacted["occurred_at"] == "2026-05-15T12:00:00+00:00"


def test_token_uuid_fields_become_a_distinct_surrogate() -> None:
    token_map = TokenMap()
    redacted = redact_tier1_payload("AgentDefined", _agent_defined_payload(), token_map=token_map)
    assert redacted["agent_id"] == token_map.token_uuid(_AGENT_ID)
    assert redacted["agent_id"] != _AGENT_ID
    assert redacted["prompt_template_id"] != _PROMPT_TEMPLATE_ID


def test_recursed_value_object_drops_its_own_drop_text_subfields() -> None:
    """model_ref is a recursed VO whose 3 fields are all drop:text."""
    redacted = redact_tier1_payload("AgentDefined", _agent_defined_payload(), token_map=TokenMap())
    assert "model_ref" not in redacted or redacted["model_ref"] == {}


def test_a_payload_key_absent_from_a_known_events_field_list_drops() -> None:
    """Schema evolution: an older schema_version's row can carry a field
    the current dataclass no longer declares. Must drop, not abort --
    aborting would make every export containing legacy-schema rows fail."""
    payload = _agent_defined_payload()
    payload["a_field_removed_in_a_later_schema_version"] = "still in an old row"
    redacted = redact_tier1_payload("AgentDefined", payload, token_map=TokenMap())
    assert "a_field_removed_in_a_later_schema_version" not in redacted
    # The known fields are still processed normally.
    assert redacted["daily_token_cap"] == 1000


def test_unknown_event_type_aborts() -> None:
    with pytest.raises(UnknownEventTypeError) as excinfo:
        redact_tier1_payload("TotallyMadeUpEventType", {}, token_map=TokenMap())
    assert excinfo.value.event_type == "TotallyMadeUpEventType"


def _stream_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "position": 999,
        "version": 999,
        "transaction_id": "12345",
        "schema_version": 1,
        "stream_type": "Agent",
        "event_type": "AgentDefined",
        "occurred_at": "2026-05-15T12:00:00+00:00",
        "recorded_at": "2026-05-15T12:00:01+00:00",
        "stream_id": str(uuid4()),
        "correlation_id": str(uuid4()),
        "causation_id": None,
        "event_id": str(uuid4()),
        "principal_id": str(uuid4()),
        "metadata": {"some": "metadata"},
        "signature": "deadbeef",
        "signature_kid": "key-1",
        "signature_version": "v1",
        "payload": _agent_defined_payload(),
    }
    row.update(overrides)
    return row


def test_metadata_and_signature_columns_are_absent_from_the_redacted_row() -> None:
    redacted = Tier1Redactor(TokenMap()).redact_row(_stream_row())
    assert "metadata" not in redacted
    assert "signature" not in redacted
    assert "signature_kid" not in redacted
    assert "signature_version" not in redacted


def test_position_is_dense_from_one_across_calls() -> None:
    redactor = Tier1Redactor(TokenMap())
    first = redactor.redact_row(_stream_row(position=4400))
    second = redactor.redact_row(_stream_row(position=9100))
    assert first["position"] == 1
    assert second["position"] == 2


def test_version_is_dense_per_stream_and_independent_across_streams() -> None:
    redactor = Tier1Redactor(TokenMap())
    stream_a = str(uuid4())
    stream_b = str(uuid4())
    a1 = redactor.redact_row(_stream_row(stream_id=stream_a, version=1))
    b1 = redactor.redact_row(_stream_row(stream_id=stream_b, version=1))
    a2 = redactor.redact_row(_stream_row(stream_id=stream_a, version=2))
    assert a1["version"] == 1
    assert b1["version"] == 1
    assert a2["version"] == 2


def test_transaction_id_is_a_small_monotone_int_not_the_raw_value() -> None:
    redactor = Tier1Redactor(TokenMap())
    first = redactor.redact_row(_stream_row(transaction_id="99999999"))
    second_same_tx = redactor.redact_row(_stream_row(transaction_id="99999999"))
    third_new_tx = redactor.redact_row(_stream_row(transaction_id="100000000"))
    assert first["transaction_id"] == 1
    assert second_same_tx["transaction_id"] == 1  # same raw tx -> same dense id
    assert third_new_tx["transaction_id"] == 2
    assert third_new_tx["transaction_id"] != 100000000


def test_stream_id_correlation_id_and_event_id_are_tokened() -> None:
    token_map = TokenMap()
    raw_stream_id = str(uuid4())
    row = _stream_row(stream_id=raw_stream_id)
    redacted = Tier1Redactor(token_map).redact_row(row)
    assert redacted["stream_id"] == token_map.token_uuid(raw_stream_id)
    assert redacted["stream_id"] != raw_stream_id


def test_causation_id_none_stays_none() -> None:
    redacted = Tier1Redactor(TokenMap()).redact_row(_stream_row(causation_id=None))
    assert redacted["causation_id"] is None


def test_fired_fields_records_declared_keys_actually_present_on_a_row() -> None:
    """The tier-1 completeness twin to tier-2's `fired_pointers`: every
    declared field key on the payload that had a real disposition entry,
    not just a snapshot of the payload's own keys."""
    fired: dict[str, set[str]] = {}
    redact_tier1_payload(
        "AgentDefined", _agent_defined_payload(), token_map=TokenMap(), fired_fields=fired
    )
    assert "agent_id" in fired["AgentDefined"]
    assert "daily_token_cap" in fired["AgentDefined"]


def test_fired_fields_excludes_an_unlisted_key_that_only_dropped_by_omission() -> None:
    """A key with no table entry (schema-evolution drop) is not a fired
    RULE: nothing in the disposition table was exercised by it."""
    fired: dict[str, set[str]] = {}
    payload = _agent_defined_payload()
    payload["a_field_removed_in_a_later_schema_version"] = "still in an old row"
    redact_tier1_payload("AgentDefined", payload, token_map=TokenMap(), fired_fields=fired)
    assert "a_field_removed_in_a_later_schema_version" not in fired["AgentDefined"]


def test_fired_fields_defaults_to_none_and_costs_nothing_when_omitted() -> None:
    """Existing callers that never pass `fired_fields` keep working."""
    redacted = redact_tier1_payload("AgentDefined", _agent_defined_payload(), token_map=TokenMap())
    assert redacted["daily_token_cap"] == 1000


def test_tier1_redactor_exposes_fired_fields_per_event_type_accumulated_across_rows() -> None:
    redactor = Tier1Redactor(TokenMap())
    redactor.redact_row(_stream_row(event_type="AgentDefined"))
    fired = redactor.fired_fields
    assert "AgentDefined" in fired
    assert "agent_id" in fired["AgentDefined"]


def test_tier1_redactor_fired_fields_is_a_copy_not_a_live_view() -> None:
    redactor = Tier1Redactor(TokenMap())
    redactor.redact_row(_stream_row())
    snapshot = redactor.fired_fields
    redactor.redact_row(
        _stream_row(event_type="AgentSuspended", payload={"agent_id": str(uuid4())})
    )
    assert "AgentSuspended" not in snapshot

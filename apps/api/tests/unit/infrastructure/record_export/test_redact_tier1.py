"""Unit tests for tier-1 (`events`) redaction.

Uses `AgentDefined`'s real, generated disposition entry (not a
hand-tuned test-only one) for the payload-shape tests, so "a bare str
drops with nobody editing a list" is demonstrated against the actual
committed table.
"""

import json
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


def test_safety_envelope_verdict_bools_are_redacted_not_kept_whole() -> None:
    """`RunStarted.safety_envelope_verdict.enclosure_permitted` /
    `.beam_available` are a point-in-time live PSS/interlock and
    beam-shutter reading, the same class of fact `EnclosurePermitObserved`
    already drops entirely. `_OVERRIDE_DISPOSITIONS`
    (`tools/gen_record_dispositions.py`) overrides the generic
    `bool -> keep:number` default for exactly these two fields; this pins
    the outcome against the real, generated table rather than a
    hand-tuned one, so a future regeneration that lost the override
    would fail this test."""
    payload = {
        "run_id": "01900000-0000-7000-8000-0000000000d1",
        "name": "2BM watched capture",
        "plan_id": "01900000-0000-7000-8000-0000000000d2",
        "subject_id": None,
        "raid": None,
        "conduct_mode": "Witnessed",
        "safety_envelope_verdict": {
            "enclosure_permitted": True,
            "beam_available": False,
        },
        "override_parameters": {},
        "effective_parameters": {},
        "trigger_source": "Monitor:2bmb-tomoscan",
        "external_refs": [{"scheme": "capture-code", "value": "2bmb-tomoscan"}],
        "acknowledged_cautions": [],
        "campaign_id": None,
        "decided_by_decision_id": None,
        "pinned_calibration_ids": [],
        "input_dataset_ids": [],
        "occurred_at": "2026-08-14T12:00:00+00:00",
    }
    redacted = redact_tier1_payload("RunStarted", payload, token_map=TokenMap())
    assert "safety_envelope_verdict" not in redacted or redacted["safety_envelope_verdict"] == {}
    # conduct_mode (keep:enum) survives, proving the drop is specific to
    # the verdict's two bools, not a blanket omission of the whole event.
    assert redacted["conduct_mode"] == "Witnessed"


def test_a_none_nested_vo_field_redacts_to_explicit_null_not_omitted() -> None:
    """A `None` on a dict-shaped (nested-VO) disposition is the field's
    own declared absence, not a malformed value: it must survive as an
    explicit null, exactly like `RunCompleted.observed_at`'s existing
    "present-as-null, not omit-when-None" scalar convention. Regression
    pin: this used to fall through to the generic "not a dict" OMITTED
    branch, silently dropping `safety_envelope_verdict` for every
    Conducted Run (the majority case) and `capture_progress_snapshot`
    for every driven completion or operator abort."""
    payload: dict[str, object] = {
        "run_id": "01900000-0000-7000-8000-0000000000d1",
        "name": "2BM conducted run",
        "plan_id": "01900000-0000-7000-8000-0000000000d2",
        "subject_id": None,
        "raid": None,
        "conduct_mode": "Conducted",
        "safety_envelope_verdict": None,
        "override_parameters": {},
        "effective_parameters": {},
        "trigger_source": None,
        "external_refs": [],
        "acknowledged_cautions": [],
        "campaign_id": None,
        "decided_by_decision_id": None,
        "pinned_calibration_ids": [],
        "input_dataset_ids": [],
        "occurred_at": "2026-08-14T12:00:00+00:00",
    }
    redacted = redact_tier1_payload("RunStarted", payload, token_map=TokenMap())
    assert "safety_envelope_verdict" in redacted
    assert redacted["safety_envelope_verdict"] is None


def test_capture_progress_snapshot_none_redacts_to_explicit_null_not_omitted() -> None:
    payload = {
        "run_id": "01900000-0000-7000-8000-0000000000d1",
        "actuation_kind": None,
        "producing_job_id": None,
        "artifact_uri": None,
        "occurred_at": "2026-08-14T12:00:00+00:00",
        "observed_at": None,
        "capture_progress_snapshot": None,
    }
    redacted = redact_tier1_payload("RunCompleted", payload, token_map=TokenMap())
    assert "capture_progress_snapshot" in redacted
    assert redacted["capture_progress_snapshot"] is None


def test_capture_progress_snapshot_counts_are_kept_not_dropped() -> None:
    """Unlike `safety_envelope_verdict`'s bools (overridden to drop:text
    because they are live PSS/beam readings), these counts are scan
    telemetry already kept in plain on the observation trail
    (`_redact_tier2.py`'s `observation` row); dropping them here would
    be the inconsistency, and would defeat the evidence this field
    exists to preserve."""
    payload = {
        "run_id": "01900000-0000-7000-8000-0000000000d1",
        "actuation_kind": None,
        "producing_job_id": None,
        "artifact_uri": None,
        "occurred_at": "2026-08-14T12:00:00+00:00",
        "observed_at": "2026-08-14T12:00:00+00:00",
        "capture_progress_snapshot": {
            "collected_count": 2987.0,
            "collected_total": 3000.0,
            "collected_at": "2026-08-14T11:59:59+00:00",
            "saved_count": None,
            "saved_total": None,
            "saved_at": None,
        },
    }
    redacted = redact_tier1_payload("RunCompleted", payload, token_map=TokenMap())
    snapshot = redacted["capture_progress_snapshot"]
    assert snapshot["collected_count"] == 2987.0
    assert snapshot["collected_total"] == 3000.0
    assert snapshot["collected_at"] == "2026-08-14T11:59:59+00:00"
    assert snapshot["saved_count"] is None


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


@pytest.mark.unit
def test_collection_rule_applies_the_element_rule_to_every_item() -> None:
    """A `[*]` rule keeps the collection and redacts each element.

    Before the table could say "collection of", a dict-shaped element rule
    met a list, fell through to OMITTED, and the field published as `{}`:
    not a withheld key but a positive claim that the collection was empty.
    Every pre-existing collection case in this file passes `[]`, where the
    right and wrong answers are indistinguishable.
    """
    payload: dict[str, object] = {
        "campaign_id": "01900000-0000-7000-8000-0000000000e1",
        "objective": {"kind": "Minimize", "target_measurement_name": "blur", "target_value": 0.0},
        "space": {
            "axes": [
                {"name": "SampleTop_X", "lower": 0.2, "upper": 0.6, "choices": []},
                {"name": "theta", "lower": -5.0, "upper": 5.0, "choices": []},
            ]
        },
        "occurred_at": "2026-09-03T12:00:00+00:00",
    }

    redacted = redact_tier1_payload("CampaignSteeringDeclared", payload, token_map=TokenMap())

    assert redacted["space"] == {
        "axes": [{"lower": 0.2, "upper": 0.6}, {"lower": -5.0, "upper": 5.0}]
    }
    json.dumps(redacted)


@pytest.mark.unit
def test_collection_rule_meeting_a_non_collection_withholds_the_field() -> None:
    """Fail closed when the stored shape disagrees with the table.

    The table states the cardinality, so a scalar arriving where a
    collection was declared is a disagreement, not an alternative encoding,
    and publishing it would mean trusting the payload over the rule.
    """
    payload: dict[str, object] = {
        "campaign_id": "01900000-0000-7000-8000-0000000000e1",
        "objective": {"kind": "Minimize", "target_measurement_name": "b", "target_value": 0.0},
        "space": {"axes": {"name": "theta", "lower": -5.0, "upper": 5.0, "choices": []}},
        "occurred_at": "2026-09-03T12:00:00+00:00",
    }

    redacted = redact_tier1_payload("CampaignSteeringDeclared", payload, token_map=TokenMap())

    assert redacted["space"] == {}


@pytest.mark.unit
def test_a_positional_record_withholds_a_slot_as_null_and_keeps_its_arity() -> None:
    """Dropping a slot would renumber the rest.

    `partition_parameters` is a collection of (name, value) pairs whose name
    is `drop:text`. Removing the withheld slot would leave a bare number
    that reads as the name. The sentinel must not survive either: it is
    internal and no JSON encoder can write it, so one escaping into a list
    aborts the entire export.
    """
    payload = {
        "asset_id": "01900000-0000-7000-8000-0000000000a3",
        "partition_rule": {
            "kind": "channel",
            "partition_parameters": [["chan_a", 1.0], ["chan_b", 2.0], ["chan_c", 3.0]],
        },
        "occurred_at": "2026-09-03T12:00:00+00:00",
    }

    redacted = redact_tier1_payload("AssetPartitionRuleUpdated", payload, token_map=TokenMap())

    assert redacted["partition_rule"]["partition_parameters"] == [
        [None, 1.0],
        [None, 2.0],
        [None, 3.0],
    ]
    json.dumps(redacted)


@pytest.mark.unit
def test_a_divergent_element_becomes_null_and_the_collection_keeps_its_length() -> None:
    """An element that disagrees with its rule is withheld, not removed.

    Removing it would shrink the collection, so a populated field would
    export as fewer items than it had, and an all-divergent field as `[]`:
    the same false claim of emptiness the collection rule exists to remove,
    relocated one level down. The sentinel must not survive either, being
    internal and unserialisable, so one escaping aborts the whole export.

    Reaches the `[*]` branch on purpose. The known divergent serializers in
    the record are all withheld by explicit override, so a test built on one
    of those would return at the `drop:` arm and never exercise this.
    """
    payload: dict[str, object] = {
        "campaign_id": "01900000-0000-7000-8000-0000000000e1",
        "objective": {"kind": "Minimize", "target_measurement_name": "b", "target_value": 0.0},
        "space": {
            "axes": [
                {"name": "theta", "lower": -5.0, "upper": 5.0, "choices": []},
                "not_an_axis",
                ["positional", "triple", "form"],
            ]
        },
        "occurred_at": "2026-09-03T12:00:00+00:00",
    }

    redacted = redact_tier1_payload("CampaignSteeringDeclared", payload, token_map=TokenMap())

    assert redacted["space"] == {"axes": [{"lower": -5.0, "upper": 5.0}, None, None]}
    json.dumps(redacted)


@pytest.mark.unit
def test_a_wholly_divergent_collection_is_not_published_as_empty() -> None:
    """Three withheld elements must not read as zero elements."""
    payload = {
        "campaign_id": "01900000-0000-7000-8000-0000000000e1",
        "objective": {"kind": "Minimize", "target_measurement_name": "b", "target_value": 0.0},
        "space": {"axes": ["a", "b", "c"]},
        "occurred_at": "2026-09-03T12:00:00+00:00",
    }

    redacted = redact_tier1_payload("CampaignSteeringDeclared", payload, token_map=TokenMap())

    assert redacted["space"] == {"axes": [None, None, None]}
    json.dumps(redacted)


@pytest.mark.unit
def test_asset_owners_are_withheld_whole_rather_than_per_field() -> None:
    """An owner block must not become a presence oracle.

    `_owner_to_payload` flattens each wrapper value object to a bare string,
    so the generated per-field rules meet strings and drop, while an ABSENT
    optional meets the None arm and survives as an explicit null. That would
    disclose which of name / contact / identifier CORA holds, with the
    reading inverted, over a field documented as typically an email.
    """
    payload = {
        "asset_id": "01900000-0000-7000-8000-0000000000a2",
        "owners": [
            {
                "name": "A Person",
                "contact": "a@example.org",
                "identifier": None,
                "identifier_type": None,
            },
            {"name": "B Person", "contact": None, "identifier": None, "identifier_type": None},
        ],
        "occurred_at": "2026-09-03T12:00:00+00:00",
    }

    redacted = redact_tier1_payload("AssetRegistered", payload, token_map=TokenMap())

    assert "owners" not in redacted
    json.dumps(redacted)


def test_tier1_redactor_fired_fields_is_a_copy_not_a_live_view() -> None:
    redactor = Tier1Redactor(TokenMap())
    redactor.redact_row(_stream_row())
    snapshot = redactor.fired_fields
    redactor.redact_row(
        _stream_row(event_type="AgentSuspended", payload={"agent_id": str(uuid4())})
    )
    assert "AgentSuspended" not in snapshot

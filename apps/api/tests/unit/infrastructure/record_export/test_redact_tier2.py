"""Unit tests for tier-2 (`entries_*`) redaction: the hand-authored
per-kind disposition table, jsonb recursion, and the unfired-clearance
report."""

from uuid import uuid4

import pytest

from cora.infrastructure.record_export import TokenMap
from cora.infrastructure.record_export._redact_tier2 import (
    TIER2_DISPOSITIONS,
    redact_tier2_row,
    unfired_clearances,
)


def test_proved_closed_text_column_survives() -> None:
    """conduit_verdicts.decision: DB CHECK (decision IN ('Allow','Deny'))."""
    row = {"event_id": str(uuid4()), "decision": "Allow"}
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("verdict", row, token_map=TokenMap(), fired_pointers=fired)
    assert redacted["decision"] == "Allow"


def test_judged_low_risk_text_column_survives() -> None:
    row = {"event_id": str(uuid4()), "command_name": "AppendActivities"}
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("verdict", row, token_map=TokenMap(), fired_pointers=fired)
    assert redacted["command_name"] == "AppendActivities"


def test_dropped_text_column_is_omitted() -> None:
    """conduit_verdicts.reason: P0-4, builds free text that can republish
    a tokened UUID."""
    row = {"event_id": str(uuid4()), "reason": "Principal ... not in policy"}
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("verdict", row, token_map=TokenMap(), fired_pointers=fired)
    assert "reason" not in redacted


def test_uuid_column_is_tokened() -> None:
    token_map = TokenMap()
    raw = str(uuid4())
    row = {"event_id": raw}
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("verdict", row, token_map=token_map, fired_pointers=fired)
    assert redacted["event_id"] == token_map.token_uuid(raw)
    assert redacted["event_id"] != raw


def test_a_column_absent_from_the_disposition_table_is_omitted() -> None:
    """Fail closed: an entries column this file never enumerated drops,
    same posture as tier 1's missing-key rule."""
    row = {"event_id": str(uuid4()), "a_column_nobody_listed": "surprise"}
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("verdict", row, token_map=TokenMap(), fired_pointers=fired)
    assert "a_column_nobody_listed" not in redacted


def test_activities_payload_keeps_cleared_string_leaves_and_drops_others() -> None:
    row = {
        "event_id": str(uuid4()),
        "payload": {
            "channel": "T_oven",
            "target_value": 423.0,
            "units": "K",
            "action_name": "open_valve",
            "an_uncleared_free_text_field": "should drop",
        },
    }
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("activity", row, token_map=TokenMap(), fired_pointers=fired)
    payload = redacted["payload"]
    assert payload["channel"] == "T_oven"
    assert payload["units"] == "K"
    assert payload["action_name"] == "open_valve"
    assert payload["target_value"] == 423.0
    assert "an_uncleared_free_text_field" not in payload


def test_activities_payload_tokens_a_uuid_shaped_string_leaf() -> None:
    token_map = TokenMap()
    raw = str(uuid4())
    row = {"event_id": str(uuid4()), "payload": {"asset_id": raw}}
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("activity", row, token_map=token_map, fired_pointers=fired)
    assert redacted["payload"]["asset_id"] == token_map.token_uuid(raw)


def test_outcomes_measurements_keeps_cleared_pointers_and_drops_quality_detail() -> None:
    row = {
        "event_id": str(uuid4()),
        "measurements": [
            {
                "name": "flux",
                "value": 1.23,
                "kind": "Scalar",
                "quality": "Good",
                "quality_detail": "opaque forensic string",
                "units": "cps",
            }
        ],
    }
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("outcome", row, token_map=TokenMap(), fired_pointers=fired)
    measurement = redacted["measurements"][0]
    assert measurement["name"] == "flux"
    assert measurement["units"] == "cps"
    assert measurement["kind"] == "Scalar"
    assert measurement["quality"] == "Good"
    assert measurement["value"] == 1.23
    assert "quality_detail" not in measurement


def test_decision_inferences_messages_drops_whole() -> None:
    row = {"event_id": str(uuid4()), "messages": [{"role": "user", "content": "secret prompt"}]}
    fired: dict[tuple[str, str], set[str]] = {}
    redacted = redact_tier2_row("inference", row, token_map=TokenMap(), fired_pointers=fired)
    assert "messages" not in redacted


@pytest.mark.parametrize("kind", sorted(TIER2_DISPOSITIONS))
def test_every_declared_kind_has_at_least_one_uuid_scope_column(kind: str) -> None:
    """Sanity check on the hand-authored table itself: every kind has at
    least one `token` column (its logbook_id/run_id/enclosure_id scope
    column at minimum)."""
    assert "token" in TIER2_DISPOSITIONS[kind].values()


def test_unfired_clearance_names_the_pointer_that_never_matched() -> None:
    """A narrow export (one setpoint, no units) is a normal export, not
    an error: CORRECTED 2026-08-12, this used to raise. See
    `unfired_clearances`'s own docstring for why raising here was a
    denylist-shaped mistake applied to an allowlist mechanism."""
    # No channel/action_name/units in this payload.
    row = {"event_id": str(uuid4()), "payload": {"target_value": 423.0}}
    fired: dict[tuple[str, str], set[str]] = {}
    redact_tier2_row("activity", row, token_map=TokenMap(), fired_pointers=fired)

    unfired = unfired_clearances(fired, kinds_present=frozenset({"activity"}))

    assert unfired == {
        ("activity", "payload", "channel"),
        ("activity", "payload", "action_name"),
        ("activity", "payload", "units"),
    }


def test_unfired_clearance_for_a_kind_not_present_reports_empty() -> None:
    """An unused clearance for a kind with zero rows in this export is
    not a completeness gap -- nothing exported to have exercised it."""
    assert unfired_clearances({}, kinds_present=frozenset({"verdict"})) == frozenset()


def test_all_declared_clearances_fired_reports_empty() -> None:
    row = {
        "event_id": str(uuid4()),
        "payload": {"channel": "T_oven", "action_name": "open_valve", "units": "K"},
    }
    fired: dict[tuple[str, str], set[str]] = {}
    redact_tier2_row("activity", row, token_map=TokenMap(), fired_pointers=fired)

    assert unfired_clearances(fired, kinds_present=frozenset({"activity"})) == frozenset()

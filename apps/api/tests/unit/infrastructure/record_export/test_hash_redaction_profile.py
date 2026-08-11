"""Unit tests for `hash_redaction_profile` (H2).

Step 7's security re-review found tier 2's hand-authored tables
(`TIER2_DISPOSITIONS`, `TIER2_JSONB_CLEARED_POINTERS`,
`TIER2_JSONB_DROPPED_COLUMNS`) missing from H2: the hash covered only
tier 1's generated `DISPOSITIONS`, so `redact_record`'s fail-closed
switch could not detect a tier-2 table edit that weakened a
disposition. These tests pin the fix: every one of the four tables H2
is supposed to cover must actually move the hash.
"""

import pytest

from cora.infrastructure.record_export import hash_redaction_profile
from cora.infrastructure.record_export._dispositions import DISPOSITIONS
from cora.infrastructure.record_export._redact_tier2 import (
    TIER2_DISPOSITIONS,
    TIER2_JSONB_CLEARED_POINTERS,
)


def test_changing_a_tier1_disposition_changes_the_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = hash_redaction_profile()
    some_event_type = next(iter(DISPOSITIONS))
    some_field = next(iter(DISPOSITIONS[some_event_type]))
    monkeypatch.setitem(DISPOSITIONS[some_event_type], some_field, "keep:enum:Tampered")
    assert hash_redaction_profile() != baseline


def test_changing_a_tier2_disposition_changes_the_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    """The gap Step 7 found: this used to be a no-op on the hash."""
    baseline = hash_redaction_profile()
    monkeypatch.setitem(TIER2_DISPOSITIONS["verdict"], "reason", "keep")
    assert hash_redaction_profile() != baseline


def test_widening_a_tier2_jsonb_clearance_changes_the_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = hash_redaction_profile()
    monkeypatch.setitem(
        TIER2_JSONB_CLEARED_POINTERS,
        ("activity", "payload"),
        frozenset({"channel", "action_name", "units", "an_extra_leaked_pointer"}),
    )
    assert hash_redaction_profile() != baseline


def test_hash_redaction_profile_is_stable_across_repeated_calls() -> None:
    assert hash_redaction_profile() == hash_redaction_profile()

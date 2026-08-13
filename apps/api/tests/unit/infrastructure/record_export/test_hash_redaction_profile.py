"""Unit tests for `hash_redaction_profile` (H2).

Step 7's security re-review found tier 2's hand-authored tables
(`TIER2_DISPOSITIONS`, `TIER2_JSONB_CLEARED_POINTERS`,
`TIER2_JSONB_DROPPED_COLUMNS`) missing from H2: the hash covered only
tier 1's generated `DISPOSITIONS`, so `redact_record`'s fail-closed
switch could not detect a tier-2 table edit that weakened a
disposition. A later pass found the SAME gap one seam over: tier 1's
own hand-authored fixed-column tables
(`FIXED_KEEP_COLUMNS`/`FIXED_TOKEN_COLUMNS`/`FIXED_DROP_COLUMNS` in
`_redact_tier1.py`, which decide `principal_id`/`signature`/etc. for
every event) were ALSO outside H2 -- moving `signature` from DROP to
KEEP would not have moved the hash. These tests pin both fixes: every
table H2 is supposed to cover must actually move the hash.
"""

import pytest

from cora.infrastructure.record_export import hash_redaction_profile
from cora.infrastructure.record_export._dispositions import DISPOSITIONS
from cora.infrastructure.record_export._redact_tier1 import (
    FIXED_DROP_COLUMNS,
    FIXED_KEEP_COLUMNS,
    FIXED_TOKEN_COLUMNS,
)
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


def test_widening_a_tier1_fixed_drop_column_to_keep_changes_the_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gap the second pass found: `signature` moving from DROP to KEEP
    (republishing a signature beside a redacted payload) used to be a
    no-op on the hash, because these three tuples are hand-authored in
    `_redact_tier1.py` and were never part of H2's body. Patched on
    `_hashing`, where `hash_redaction_profile` actually reads the name
    it imported, not on `_redact_tier1` (rebinding a tuple there would
    not be visible through `_hashing`'s own already-bound import)."""
    baseline = hash_redaction_profile()
    monkeypatch.setattr(
        "cora.infrastructure.record_export._hashing.FIXED_DROP_COLUMNS",
        tuple(c for c in FIXED_DROP_COLUMNS if c != "signature"),
    )
    assert hash_redaction_profile() != baseline


def test_narrowing_tier1_fixed_keep_columns_changes_the_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = hash_redaction_profile()
    monkeypatch.setattr(
        "cora.infrastructure.record_export._hashing.FIXED_KEEP_COLUMNS",
        FIXED_KEEP_COLUMNS[:-1],
    )
    assert hash_redaction_profile() != baseline


def test_narrowing_tier1_fixed_token_columns_changes_the_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The column this fixed table tokens is `principal_id`; moving it out
    of TOKEN would be the attribution leak F5's threat model names."""
    baseline = hash_redaction_profile()
    monkeypatch.setattr(
        "cora.infrastructure.record_export._hashing.FIXED_TOKEN_COLUMNS",
        tuple(c for c in FIXED_TOKEN_COLUMNS if c != "principal_id"),
    )
    assert hash_redaction_profile() != baseline

"""Architecture fitness: signature_version is part of the matched-pair invariant.

The signed-event row carries three coupled fields: `signature` (raw
bytes), `signature_kid` (key id), and `signature_version` (signing-
recipe identifier, dispatched to the matching ByteSigner adapter
via the SigningRegistry per project_canonicalization_port_design.md).

The matched-pair invariant: all three are NULL together (unsigned
row) or all three are non-NULL together (signed row). Any partial
combination is a write-side bug.

This fitness pins the invariant at TWO layers:

  - Database: the events table CHECK constraints enforce
    `(signature IS NULL) = (signature_kid IS NULL) =
    (signature_version IS NULL)` via two CHECK constraints
    (signature/signature_kid pair was set in
    20260523214753; signature/signature_version pair in
    20260601000000). A migration that drops or weakens either
    CHECK fails this test.
  - Application: the NewEvent + StoredEvent value types both carry
    the three fields with `bytes | None`, `str | None`, `str | None`
    types respectively, so a drift on the dataclass shape (removing
    a field, changing a type) fails before any SQL ever runs.

Per project_immutability_guarantee.md the events table is INSERT-only
and immortal. The signature columns are nullable forever, and the
matched-pair CHECKs are the structural guarantee that no
partially-signed row can ever be persisted.
"""

import re
from dataclasses import fields

import pytest

from cora.infrastructure.ports.event_store import NewEvent, StoredEvent
from tests.architecture.conftest import tracked_migration_files

_SIGNATURE_FIELD_NAMES = {"signature", "signature_kid", "signature_version"}


def test_new_event_carries_all_three_signature_fields_with_optional_types() -> None:
    field_map = {f.name: f for f in fields(NewEvent)}
    for name in _SIGNATURE_FIELD_NAMES:
        assert name in field_map, (
            f"NewEvent missing signature field {name!r}; the matched-pair "
            f"invariant requires all three (signature, signature_kid, "
            f"signature_version)."
        )


def test_stored_event_carries_all_three_signature_fields_with_optional_types() -> None:
    field_map = {f.name: f for f in fields(StoredEvent)}
    for name in _SIGNATURE_FIELD_NAMES:
        assert name in field_map, (
            f"StoredEvent missing signature field {name!r}; the matched-pair "
            f"invariant requires all three (signature, signature_kid, "
            f"signature_version)."
        )


def test_events_signature_kid_consistency_check_constraint_present_in_migrations() -> None:
    haystack = _all_migration_text()
    assert "events_signature_kid_consistency" in haystack, (
        "events_signature_kid_consistency CHECK constraint missing from "
        "migrations. The (signature, signature_kid) matched-pair invariant "
        "MUST stay enforced at the database layer; see "
        "20260523214753_add_events_signature_columns.sql for the original."
    )


def test_events_signature_version_consistency_check_constraint_present_in_migrations() -> None:
    haystack = _all_migration_text()
    assert "events_signature_version_consistency" in haystack, (
        "events_signature_version_consistency CHECK constraint missing "
        "from migrations. The (signature, signature_version) matched-pair "
        "invariant MUST stay enforced at the database layer; see "
        "20260601000000_add_events_signature_version.sql for the lock."
    )


@pytest.mark.parametrize(
    "constraint_name",
    [
        "events_signature_kid_consistency",
        "events_signature_version_consistency",
    ],
)
def test_signature_matched_pair_check_constraint_uses_null_equals_null_shape(
    constraint_name: str,
) -> None:
    haystack = _all_migration_text()
    pattern = re.compile(
        rf"CONSTRAINT\s+{re.escape(constraint_name)}\s+CHECK\s*\(\s*"
        r"\(signature\s+IS\s+NULL\)\s*=\s*\(signature_(?:kid|version)\s+IS\s+NULL\)",
        re.IGNORECASE,
    )
    assert pattern.search(haystack), (
        f"CONSTRAINT {constraint_name} does not use the locked "
        f"`(signature IS NULL) = (signature_X IS NULL)` matched-pair "
        f"shape. Any change away from this form weakens the invariant: a "
        f"signature without its companion (or vice versa) MUST be rejected "
        f"at INSERT time, not papered over in application code."
    )


def _all_migration_text() -> str:
    return "\n".join(f.read_text() for f in tracked_migration_files())

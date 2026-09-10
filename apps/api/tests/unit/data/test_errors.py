"""Unit tests for `cora.data.errors`.

`ScanFileInvalidReason` is the discriminated, non-PII reason
`InvalidScanFileError` carries so a caller can branch on cause without
parsing `str(exc)` or ever touching a path it may embed. These tests
pin the two properties that make that safe to rely on: the
permanent/transient split is real, not a single bucket everything falls
into, and every member's value stays safe to log and persist forever.
"""

import pytest

from cora.data.errors import ScanFileInvalidReason

pytestmark = pytest.mark.unit

# Mirrors the deny-list STYLE of _PII_FIELD_NAMES in
# tests/architecture/test_run_events_carry_no_pii.py, duplicated rather
# than imported because that module fitness-tests a different file's
# dataclass field NAMES; this checks arbitrary substrings of an enum
# VALUE instead, a different shape of check over the same hazard.
# Compared case-folded against the PascalCase value, so "Path" and
# "PATH" are both caught.
_PII_TOKENS = frozenset(
    {
        "path",
        "directory",
        "surname",
        "lastname",
        "proposal",
        "esaf",
        "username",
        "userbadge",
        "useremail",
        "institution",
    }
)


def test_scan_file_invalid_reason_transient_and_permanent_members_are_distinct() -> None:
    """Mutation check: an enum where every member shared one
    `is_transient` verdict would still let a badly-collapsed handler
    compile and run, silently condemning transient failures as
    permanent. Asserting both buckets are populated, disjoint, and that
    a representative transient/permanent pair differ is the failure
    this guards against; `test_ingest_scan_handler.py`'s
    `test_ingest_transient_and_permanent_refusals_yield_different_reasons`
    is the stronger sibling, driven through the actual handler's raise
    sites rather than the enum definition alone."""
    transient = {member for member in ScanFileInvalidReason if member.is_transient}
    permanent = {member for member in ScanFileInvalidReason if not member.is_transient}

    assert transient, "at least one member must be transient"
    assert permanent, "at least one member must be permanent"
    assert transient.isdisjoint(permanent)
    assert ScanFileInvalidReason.UNREADABLE != ScanFileInvalidReason.STRUCTURALLY_INCOMPLETE
    assert ScanFileInvalidReason.UNREADABLE.is_transient
    assert not ScanFileInvalidReason.STRUCTURALLY_INCOMPLETE.is_transient


def test_scan_file_invalid_reason_values_carry_no_path_or_pii_token() -> None:
    """Every member must stay safe to log and persist forever: per the
    class docstring it must never embed, interpolate, or derive from a
    filesystem path. Checks a literal path separator and a PII-style
    token separately, since a future member named carelessly (for
    instance around a vault path) could dodge one guard while failing
    the other."""
    for member in ScanFileInvalidReason:
        value = member.value
        assert "/" not in value
        assert "\\" not in value
        lowered = value.lower()
        hits = {token for token in _PII_TOKENS if token in lowered}
        assert not hits, f"{member.name}'s value {value!r} contains PII-style token(s): {hits}"

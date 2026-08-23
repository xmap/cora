"""Pins the registered logbook kind SET against `MANIFEST_SCHEMA_VERSION`,
and separately pins each kind's CURRENT extent status.

Per `project_record_completeness_design.md`'s "Two authorities, two
times": `registered_kinds_hash` lets a reader tell whether their own
checkout's registry has grown a kind a bundle's manifest never had a
slot for, but only if the kind set and the schema version move
together. Sibling to `test_record_export_registry_completeness.py`'s
`test_exactly_six_logbook_opened_classes_exist`, which pins the six
envelope classes; this pins the full ten-kind registry (`_registry.py`
already pins the bare count in `tests/unit/infrastructure/record_export/
test_registry.py::test_registry_has_ten_entries_not_six`, but not the
SET, and not against the manifest's own version).

The tenth `EntriesTableSpec` (`supply_probe`, the BLEPS supply
observer's probe trail) landed exactly the way this docstring predicted:
a deliberate, reviewed edit to `_REGISTERED_KINDS` below plus a
`MANIFEST_SCHEMA_VERSION` bump (1 -> 2), not a silent one.

`MANIFEST_SCHEMA_VERSION` versions the kind SET pinned above, not any
kind's extent status; see the constant's own docstring in `_manifest.py`
for why a status move is not a version-bump trigger. But "not a bump
trigger" must not mean "not tracked" -- that gap (a status graduating
out of `untraversed` with nothing to catch it) is exactly how S5a, S5b
and S5c each slipped past a docstring that, at the time, claimed the
opposite. `test_extent_status_pin_matches_every_registered_kinds_current_status`
below pins the second axis so a future status change still fails
loudly and forces a reader here, even though the fix it demands is
updating this pin, not bumping the version.
"""

import pytest

from cora.infrastructure.record_export import (
    MANIFEST_SCHEMA_VERSION,
    ExportedRecord,
    LogbookKindExtentStatus,
    all_specs,
    build_manifest,
)

_REGISTERED_KINDS = (
    "activity",
    "capture_probe",
    "diagnostic",
    "heartbeat",
    "inference",
    "observation",
    "outcome",
    "permit_probe",
    "supply_probe",
    "verdict",
)

# Every registered kind's current extent status, per the S4/S5 decisions
# recorded in project_record_completeness_design.md, plus the BLEPS
# supply observer slice for supply_probe: all ten kinds are IN, and
# after S5a/S5b/S5c/the supply-probe slice wired every unscoped reader,
# none resolves UNTRAVERSED in production any more. A future kind
# losing its reader (or a new kind registered with none) changes this
# dict, which is the point: it must be a deliberate edit, not a silent
# one.
_EXTENT_STATUS_BY_KIND = {kind: LogbookKindExtentStatus.INCLUDED for kind in _REGISTERED_KINDS}


@pytest.mark.architecture
def test_registered_kinds_pin_forces_a_deliberate_schema_version_bump() -> None:
    assert tuple(sorted(spec.kind for spec in all_specs())) == _REGISTERED_KINDS, (
        "the registered logbook kind set has changed; bump MANIFEST_SCHEMA_VERSION "
        "in _manifest.py, update _REGISTERED_KINDS here, and update the S4 "
        "membership decision in project_record_completeness_design.md together"
    )
    assert MANIFEST_SCHEMA_VERSION == 2, (
        "MANIFEST_SCHEMA_VERSION moved without updating this pin's expected "
        "value; update _REGISTERED_KINDS above in the same commit"
    )


@pytest.mark.architecture
def test_extent_status_pin_matches_every_registered_kinds_current_status() -> None:
    record = ExportedRecord(streams=(), logbooks={})
    # Every registered kind is included with zero rows in this fixture, so
    # a matching source_row_count_by_logbook_kind of all zeros keeps this test about
    # status alone, not S2b's independent-count check.
    source_row_count_by_logbook_kind = {spec.kind: 0 for spec in all_specs()}
    manifest = build_manifest(
        record,
        git_commit="deadbeef",
        source_row_count_by_logbook_kind=source_row_count_by_logbook_kind,
    )
    actual = {kind: extent.status for kind, extent in manifest.extent_by_logbook_kind.items()}
    assert actual == _EXTENT_STATUS_BY_KIND, (
        "a registered kind's extent status has changed; update "
        "_EXTENT_STATUS_BY_KIND here and decide, per MANIFEST_SCHEMA_VERSION's "
        "own docstring in _manifest.py, whether this move also warrants a "
        "version bump (today: no, a status move alone never does)"
    )

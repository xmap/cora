"""Every string leaf pointer in `TIER2_JSONB_CLEARED_POINTERS` must name
a key that can actually appear in the jsonb column it clears.

This is the build-time check the removed `UnfiredClearanceError` was
standing in for (see `_redact_tier2.unfired_clearances`'s docstring).
That check ran per export and conflated two different questions: "is
this export narrow?" (not a bug) and "is this pointer typed correctly at
all?" (a real bug, most likely a hand-typed typo). This file asks only
the second question, once, against the real key space, the same shape
as step 0's generated disposition table -- resolve the truth once,
commit the check, let redaction read inert data.

Two columns, two different strengths of check, and the difference is
honest rather than hidden:

- `outcome.measurements` is backed by a real dataclass
  (`cora.operation.ports.measurement.Measurement`), so this file
  INTROSPECTS it. A misspelled pointer here fails for the same reason a
  misspelled attribute access would.
- `activity.payload` has NO typed contract. Its shape lives in
  `append_activities/route.py`'s docstring (three of the five
  `STEP_KIND_VALUES` -- setpoint/action/check; capture/compute are
  undocumented) plus in `conductor.py`'s `_append_step`, which merges in
  `step_index` / `result` / `error_class?` / `message?` on EVERY kind,
  none of which the docstring mentions. This file therefore
  HAND-ENCODES the known keys from both sources and checks against
  their union. That is a stopgap, not a fix: it catches a pointer that
  matches NO known key, but it cannot detect a typo that happens to
  collide with a different real key, and it says nothing about whether
  the CLEARED set is complete (see the note on `result` below). Step 3
  in `project_record_export_build_brief.md` -- per-kind typed payloads
  -- is what would let this become a real introspection check like the
  measurements one; it is not built.

FOUND while writing this, and NOT acted on here, because changing what
gets published is a content decision, not a typo check: `result` is
written on every conductor-driven activity row
(`conductor.py:3956` / `_append_step`) and is, in practice, drawn from
exactly three module-level string constants (`_RESULT_OK = "ok"`,
`_RESULT_FAILED = "failed"`, `_RESULT_IN_FLIGHT = "in_flight"`,
verified by grepping every `result=` call site in `conductor.py`), the
same "closed in practice, declared as bare `str`" shape as several
existing JUDGED LOW RISK tier-2 clearances. It is NOT in
`TIER2_JSONB_CLEARED_POINTERS`, so it drops on every export today,
which means the published record cannot currently distinguish a step
that succeeded from one that failed. `_KNOWN_ACTIVITY_PAYLOAD_KEYS`
below lists `result` as a known key precisely so this file's own
completeness gap is visible in its source rather than silently absent.
"""

import dataclasses

from cora.infrastructure.record_export._redact_tier2 import TIER2_JSONB_CLEARED_POINTERS
from cora.operation.ports.measurement import Measurement

# Per `append_activities/route.py`'s payload docstring (setpoint/action/
# check only) plus the envelope keys `conductor.py`'s `_append_step`
# merges into EVERY kind's payload (`step_index`, `result`, and
# `error_class` / `message` on failure). `capture` and `compute` are two
# of `STEP_KIND_VALUES`'s five members and are NOT represented here: no
# docstring or call site documents their payload shape, which is itself
# evidence for project_record_export_build_brief.md's step 3.
_KNOWN_ACTIVITY_PAYLOAD_KEYS = frozenset(
    {
        "channel",
        "target_value",
        "units",
        "ramp_rate",
        "action_name",
        "params",
        "passed",
        "expected",
        "actual",
        "tolerance",
        "step_index",
        "result",
        "error_class",
        "message",
    }
)


def test_activity_payload_clearances_are_within_the_known_key_space() -> None:
    cleared = TIER2_JSONB_CLEARED_POINTERS[("activity", "payload")]
    unknown = cleared - _KNOWN_ACTIVITY_PAYLOAD_KEYS
    assert not unknown, (
        f"TIER2_JSONB_CLEARED_POINTERS[('activity', 'payload')] clears {sorted(unknown)}, "
        "which names no key documented in append_activities/route.py or written by "
        "conductor.py's _append_step. Likely a typo; see this file's module docstring."
    )


def test_outcome_measurements_clearances_are_real_measurement_fields() -> None:
    """`*/name`, `*/units`, `*/kind`, `*/quality` per element of the
    `measurements` list: strip the `*/` list-element marker and check
    the remainder against `Measurement`'s actual dataclass fields."""
    real_fields = frozenset(f.name for f in dataclasses.fields(Measurement))
    cleared = TIER2_JSONB_CLEARED_POINTERS[("outcome", "measurements")]

    for pointer in cleared:
        assert pointer.startswith("*/"), (
            f"{pointer!r} does not use the '*/' any-list-element marker "
            "this test assumes for outcome.measurements"
        )
        field_name = pointer.removeprefix("*/")
        assert field_name in real_fields, (
            f"TIER2_JSONB_CLEARED_POINTERS[('outcome', 'measurements')] clears "
            f"{pointer!r}, but Measurement has no field {field_name!r}. "
            f"Real fields: {sorted(real_fields)}."
        )


def test_outcome_measurements_never_clears_the_opaque_diagnostic_field() -> None:
    """`quality_detail` is documented as free-form substrate forensic
    text (`measurement.py`); it must never appear in the cleared set,
    however the check above is implemented."""
    cleared = TIER2_JSONB_CLEARED_POINTERS[("outcome", "measurements")]
    assert "*/quality_detail" not in cleared

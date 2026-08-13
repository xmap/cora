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
- `activity.payload` has NO typed contract; its shape is built
  imperatively across several `Conductor` methods
  (`_run_setpoint`/`_run_action`/`_run_check`/`_run_capture`/
  `_run_compute*`) with no single dataclass or dict-literal `return` to
  introspect the way `test_record_disposition_keys_match_stored_payload.py`
  does for an event's `to_payload`. This file therefore AST-SCANS those
  methods (plus their free-function helpers) for every string dict-key
  literal actually written into source, and checks each cleared
  pointer's segments against that discovered set.

  CORRECTED 2026-08-12 (slice 6 of project_record_publishing_campaign.md).
  The PREVIOUS version of this check hand-encoded its reference set from
  `append_activities/route.py`'s payload docstring plus a manual list of
  `_record`'s envelope keys. That docstring is free text (the field is
  `payload: dict[str, Any]`, unvalidated) and, measured against
  `conductor.py`, simply describes a payload shape the Conductor has
  never written: `channel`/`target_value`/`units`/`ramp_rate` for
  setpoint (the real keys are `address`/`value`), `action_name` for
  action (the real key is `name`), `channel`/`passed`/`actual` for check
  (the real keys are `address`/`criterion`, with the verdict living only
  in `result`). Because `TIER2_JSONB_CLEARED_POINTERS` had ALSO been
  transcribed from that same docstring, the old test was checking the
  clearance list's copy of the wrong source against its own copy of the
  same wrong source: both sides agreed, so it stayed green over three
  cleared pointers -- `channel`, `action_name`, `units` -- that could
  never fire against any payload the Conductor actually writes, while
  the real fields (`address`, `name`, `criterion`, `reading`, and
  `result` itself) dropped on every export. See
  `_redact_tier2.py`'s `TIER2_JSONB_CLEARED_POINTERS` comment for the
  corrected clearance list and the disclosure rationale (threat model)
  behind each pointer.

  This AST scan is still not full introspection: it collects every
  string key used ANYWHERE inside the whitelisted functions, flattened,
  not pointer-shaped, so it cannot tell a `kind` that belongs under
  `reading` from a `kind` that belongs under `criterion`. It fails,
  loudly, on a pointer whose segment names no key the Conductor writes
  ANYWHERE -- which is precisely the failure mode that let
  `channel`/`action_name`/`units` through. A pointer that reuses a real
  key name from an unrelated part of the payload is a residual blind
  spot, the same kind `test_record_disposition_keys_match_stored_payload.py`
  documents for its own AST case. Per-kind typed payloads (Step 3 in
  `project_record_export_build_brief.md`) is what would close it for
  good.

  SCOPE: this file (and the clearance list it checks) covers ONLY the
  Conductor-driven shape. `activity.payload` has a second real writer,
  not addressed here -- see `_redact_tier2.py`'s
  `TIER2_JSONB_CLEARED_POINTERS` comment for the full account (the
  authoritative copy; do not restate it here, it drifts).
"""

import ast
import dataclasses
from pathlib import Path

from cora.infrastructure.record_export._redact_tier2 import TIER2_JSONB_CLEARED_POINTERS
from cora.operation.ports.measurement import Measurement

# Every Conductor method (or free-function helper) that builds part of a
# conducted step's `activity.payload`. Kept as an explicit whitelist,
# not "every function in the file", so an unrelated dict literal
# elsewhere in this 4000+ line module (diagnostics, outcomes, the
# decide/convergence loops) cannot loosen this check by donating a
# same-named key that happens to make a bad pointer look real.
_ACTIVITY_PAYLOAD_FUNCTIONS = frozenset(
    {
        "_record",
        "_run_setpoint",
        "_post_read_evidence",
        "_run_action",
        "_run_check",
        "_run_capture",
        "_run_compute",
        "_run_compute_artifact_arm",
        "_record_compute_capture_failure",
        "_record_compute_output_failure",
        "_record_compute_failure",
        "_criterion_to_dict",
        "_measurement_to_dict",
        "_compute_measurement_to_dict",
        "_compute_artifact_to_dict",
    }
)


def _conductor_source() -> ast.Module:
    import cora.operation.conductor as conductor_module

    return ast.parse(Path(conductor_module.__file__).read_text(encoding="utf-8"))


def _discovered_functions(tree: ast.Module) -> dict[str, ast.AST]:
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in _ACTIVITY_PAYLOAD_FUNCTIONS
    }


def _activity_payload_key_space(tree: ast.Module) -> frozenset[str]:
    """Every string dict-key literal written anywhere inside the
    whitelisted functions, flattened across nesting. See module
    docstring for what this can and cannot catch.

    Two AST shapes, both collected: a `{"key": ...}` dict literal (every
    step-body builder uses this), and a `payload["key"] = ...` subscript
    assignment (`_record` itself uses this for `error_class`/`message`).
    Today the subscript-assigned keys also happen to appear as dict
    literals elsewhere in the whitelist (`_post_read_evidence` nests
    `error_class` under `post_read_error`), so collecting only dict
    literals would still pass by coincidence -- collecting both shapes
    removes that coincidence rather than relying on it.
    """
    keys: set[str] = set()
    for node in _discovered_functions(tree).values():
        for inner in ast.walk(node):
            if isinstance(inner, ast.Dict):
                for k in inner.keys:
                    if isinstance(k, ast.Constant) and isinstance(k.value, str):
                        keys.add(k.value)
            elif (
                isinstance(inner, ast.Subscript)
                and isinstance(inner.slice, ast.Constant)
                and isinstance(inner.slice.value, str)
            ):
                keys.add(inner.slice.value)
    return frozenset(keys)


def test_every_whitelisted_activity_payload_function_still_exists() -> None:
    """A rename or removal of a whitelisted function must fail loudly
    here rather than silently shrinking the discovered key space (and
    with it, this test's ability to catch a bad pointer)."""
    tree = _conductor_source()
    discovered = set(_discovered_functions(tree))
    missing = _ACTIVITY_PAYLOAD_FUNCTIONS - discovered
    assert not missing, (
        f"{sorted(missing)} not found in conductor.py (renamed or removed). "
        "Update _ACTIVITY_PAYLOAD_FUNCTIONS in this file, or the real key "
        "space this test checks against silently narrows."
    )


def test_activity_payload_key_space_is_not_suspiciously_small() -> None:
    """A parser bug or an over-narrow whitelist would silently shrink the
    discovered key space toward empty rather than raise; this pins a
    floor so that failure mode is visible. Not a precise count -- see
    [[feedback-narrow-edits-verify-the-count]] on why a floor beats
    nothing, and [[project-record-publishing-campaign]] on why an exact
    count would just be one more number to re-measure and forget."""
    real_keys = _activity_payload_key_space(_conductor_source())
    assert len(real_keys) >= 20, (
        f"only {len(real_keys)} keys discovered across "
        f"{sorted(_ACTIVITY_PAYLOAD_FUNCTIONS)}; the AST scan may be broken."
    )


def test_activity_payload_clearances_are_real_conductor_keys() -> None:
    real_keys = _activity_payload_key_space(_conductor_source())
    cleared = TIER2_JSONB_CLEARED_POINTERS[("activity", "payload")]
    for pointer in cleared:
        segments = [segment for segment in pointer.split("/") if segment != "*"]
        unknown = [segment for segment in segments if segment not in real_keys]
        assert not unknown, (
            f"TIER2_JSONB_CLEARED_POINTERS[('activity', 'payload')] clears "
            f"{pointer!r}, whose segment(s) {unknown} name no dict key found "
            "anywhere in conductor.py's step-recording methods "
            f"({sorted(_ACTIVITY_PAYLOAD_FUNCTIONS)}). Likely a typo, or a "
            "stale pointer describing a key the Conductor no longer writes."
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

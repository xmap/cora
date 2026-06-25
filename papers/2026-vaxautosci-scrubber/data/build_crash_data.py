#!/usr/bin/env python3
"""Build the crash / in-flight figure data (Figure 3) for the paper.

This emits crash_run.json: a CORA-conducted run on the conductor path, where a
side-effecting step records a pre-effect in-flight marker before its outcome,
truncated to simulate a crash after a marker but before its outcome. The
dangling in-flight entry (a marker with no matching outcome at one step_index)
is the interrupted step the scrubber surfaces as an open interval.

Provenance. The conductor-path activity shapes and values are taken from

    apps/api/tests/integration/test_conductor_against_softioc_postgres.py

which exercises, against a real softIOC + Postgres, exactly these rows: a
setpoint pre-effect marker {address, value, step_index, result="in_flight"};
the setpoint outcome {address, value, post_reading{value,quality}, step_index,
result="ok"}; and a check {address, criterion, reading, step_index,
result="ok"}. The payload carries step_index + result per
cora/operation/conductor.py (the "{**body, step_index, result}" append and the
"Pre-effect in-flight marker" docstring). The crash is the one constructed
element: we truncate after the final setpoint's marker, per that documented
resume substrate. Channel names are the softIOC test channels with the per-test
prefix omitted for readability.

Run with the standard library only (no database).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

_BASE = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def _at(seconds: int) -> str:
    return _iso(_BASE + timedelta(seconds=seconds))


def _build() -> dict:
    # A short conducted "bakeout" sequence: setpoint (marker + ok) -> check (ok)
    # -> setpoint (marker, then crash). step_index is the position in the step
    # list; the crash leaves step_index 2 with a marker and no outcome.
    activities = [
        {
            "seq": 1,
            "step_index": 0,
            "step_kind": "setpoint",
            "result": "in_flight",
            "sampled_at": _at(0),
            "payload": {
                "address": "double_value",
                "value": 7.5,
                "step_index": 0,
                "result": "in_flight",
            },
        },
        {
            "seq": 2,
            "step_index": 0,
            "step_kind": "setpoint",
            "result": "ok",
            "sampled_at": _at(3),
            "payload": {
                "address": "double_value",
                "value": 7.5,
                "post_reading": {"value": 7.5, "quality": "Good"},
                "step_index": 0,
                "result": "ok",
            },
        },
        {
            "seq": 3,
            "step_index": 1,
            "step_kind": "check",
            "result": "ok",
            "sampled_at": _at(8),
            "payload": {
                "address": "double_value",
                "criterion": {"kind": "within_tolerance", "expected": 7.5, "tolerance": 0.01},
                "reading": {"value": 7.5},
                "step_index": 1,
                "result": "ok",
            },
        },
        {
            "seq": 4,
            "step_index": 2,
            "step_kind": "setpoint",
            "result": "in_flight",
            "sampled_at": _at(12),
            "payload": {
                "address": "long_value",
                "value": 99,
                "step_index": 2,
                "result": "in_flight",
            },
            "dangling": True,
        },
    ]

    # The interrupted step: the in-flight marker whose step_index has no outcome.
    outcomes = {a["step_index"] for a in activities if a["result"] != "in_flight"}
    markers = {a["step_index"] for a in activities if a["result"] == "in_flight"}
    interrupted = sorted(markers - outcomes)
    assert interrupted == [2], interrupted

    return {
        "provenance": {
            "source": (
                "Conductor-path activity shapes and values from "
                "apps/api/tests/integration/test_conductor_against_softioc_postgres.py "
                "(real softIOC + Postgres). Payload carries step_index + result per "
                "cora/operation/conductor.py."
            ),
            "run": "CORA-conducted bakeout-style sequence on the conductor path",
            "crash": (
                "Constructed: truncated after the final setpoint's pre-effect marker, "
                "per the resume substrate documented in conductor.py. Only the "
                "truncation is synthetic; row shapes and values are from the test."
            ),
            "channels": "softIOC test channels; per-test prefix omitted for readability",
            "timestamps": "sampled_at staggered synthetically; wall-clock spacing needs a live run",
            "generated_by": "data/build_crash_data.py",
        },
        "procedure": {
            "name": "2-BM bakeout",
            "kind": "bakeout",
            "path": "conductor",
            "crashed": True,
            "interrupted_step_index": interrupted[0],
        },
        "activities": activities,
    }


def main() -> None:
    out = Path(__file__).parent / "crash_run.json"
    data = _build()
    out.write_text(json.dumps(data, indent=2) + "\n")
    acts = data["activities"]
    print(
        f"wrote {out} : {len(acts)} activities, "
        f"interrupted step_index={data['procedure']['interrupted_step_index']}"
    )


if __name__ == "__main__":
    main()

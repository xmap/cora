#!/usr/bin/env python3
"""Build the figure data for the replay-scrubber paper.

This emits focus_run.json: a figure-oriented projection of the CORA-conducted
autofocus alignment at APS 2-BM (SampleTop_Z, a four-iteration peak-bracket
search). It is runnable with the standard library only (no database).

Provenance. The activity payloads, iteration verdicts, and reasons mirror the
authoritative run definition in

    apps/api/tests/integration/scenarios/test_2bm_alignment_focus.py

which asserts that these exact rows round-trip through the real Kernel and the
Postgres projections (entries_operation_procedure_activities,
proj_operation_procedure_iterations). If that scenario changes, update here, or
regenerate from a live testcontainers export per data/README.md.

This is the clean, completed run on the append_activities path; it carries no
in-flight markers. The crash / open-interval case (Figure 3) uses the conductor
path and is exported separately (see data/README.md).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

# The source scenario records every row at one logical instant. For a readable
# time axis we stagger sampled_at synthetically; real wall-clock spacing needs a
# live run. This is recorded in the provenance block below.
_BASE = datetime(2026, 5, 17, 11, 0, 0, tzinfo=UTC)
_ITER_STRIDE = timedelta(seconds=30)
_SETPOINT_AT = timedelta(seconds=2)
_ACTION_AT = timedelta(seconds=9)
_CHECK_AT = timedelta(seconds=12)
_ITER_SPAN = timedelta(seconds=15)
_FINALIZE_AT = timedelta(seconds=20)

_SAMPLE = "depth_phantom"


def _iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


# Per-iteration plan: (focus position mm, setpoint role, sharpness, check extras).
_ITERATIONS = [
    {
        "index": 1,
        "target_mm": 0.000,
        "role": "initial",
        "sharpness": 0.50,
        "note": "user-supplied start position",
        "converged": False,
        "reason": "initial sharpness 0.50; peak not yet bracketed",
    },
    {
        "index": 2,
        "target_mm": 0.500,
        "role": "step_positive",
        "sharpness": 0.70,
        "direction": "better",
        "converged": False,
        "reason": "sharpness improving (0.70); peak not yet bracketed",
    },
    {
        "index": 3,
        "target_mm": 1.000,
        "role": "step_positive",
        "sharpness": 0.65,
        "direction": "worse",
        "evidence": {"bracket_low_mm": 0.500, "bracket_high_mm": 1.000},
        "converged": False,
        "reason": "sharpness dropped to 0.65; peak bracketed in [0.500, 1.000]mm",
    },
    {
        "index": 4,
        "target_mm": 0.750,
        "role": "bisect",
        "sharpness": 0.74,
        "direction": "peak",
        "passed": True,
        "evidence": {"peak_position_mm": 0.750},
        "converged": True,
        "reason": None,
    },
]

_PROCEDURE_EVENTS = [
    "ProcedureRegistered",
    "ProcedureStarted",
    "ProcedureIterationStarted",
    "ProcedureActivitiesLogbookOpened",
    "ProcedureIterationEnded",
    "ProcedureIterationStarted",
    "ProcedureIterationEnded",
    "ProcedureIterationStarted",
    "ProcedureIterationEnded",
    "ProcedureIterationStarted",
    "ProcedureIterationEnded",
    "ProcedureCompleted",
]


def _build() -> dict:
    activities: list[dict] = []
    iterations: list[dict] = []
    seq = 0

    for spec in _ITERATIONS:
        i = spec["index"]
        start = _BASE + (i - 1) * _ITER_STRIDE
        end = start + _ITER_SPAN
        iterations.append(
            {
                "iteration_index": i,
                "started_at": _iso(start),
                "ended_at": _iso(end),
                "converged": spec["converged"],
                "reason": spec["reason"],
            }
        )

        setpoint_payload = {
            "channel": "SampleTop_Z",
            "target_value": spec["target_mm"],
            "units": "mm",
            "role": spec["role"],
        }
        if "note" in spec:
            setpoint_payload["note"] = spec["note"]

        check_payload = {
            "channel": "image_sharpness",
            "passed": spec.get("passed", False),
            "source": "tomopy.misc.morph",
            "actual": spec["sharpness"],
            "sample": _SAMPLE,
        }
        if "direction" in spec:
            check_payload["direction"] = spec["direction"]
        if "evidence" in spec:
            check_payload["evidence"] = spec["evidence"]

        for kind, payload, at in (
            ("setpoint", setpoint_payload, start + _SETPOINT_AT),
            (
                "action",
                {"action_name": "acquire_alignment_frame", "params": {"exposure_ms": 200}},
                start + _ACTION_AT,
            ),
            ("check", check_payload, start + _CHECK_AT),
        ):
            seq += 1
            activities.append(
                {
                    "seq": seq,
                    "iteration": i,
                    "step_kind": kind,
                    "payload": payload,
                    "sampled_at": _iso(at),
                    "result": None,
                }
            )

    # Finalize: lock at the converged peak, outside the iteration loop.
    seq += 1
    finalize_at = _BASE + 3 * _ITER_STRIDE + _FINALIZE_AT
    activities.append(
        {
            "seq": seq,
            "iteration": None,
            "step_kind": "setpoint",
            "payload": {
                "channel": "SampleTop_Z",
                "target_value": 0.750,
                "units": "mm",
                "role": "lock_at_peak",
            },
            "sampled_at": _iso(finalize_at),
            "result": None,
        }
    )

    return {
        "provenance": {
            "source": (
                "Derived from apps/api/tests/integration/scenarios/"
                "test_2bm_alignment_focus.py, the authoritative run definition, "
                "which asserts these activities and iterations round-trip through "
                "the real Kernel and Postgres projections."
            ),
            "run": (
                "CORA-conducted autofocus alignment, APS 2-BM, SampleTop_Z, "
                "four-iteration peak-bracket search"
            ),
            "path": "append_activities (clean completed run; no in-flight markers)",
            "timestamps": (
                "sampled_at staggered synthetically for a readable time axis; the "
                "source scenario records a single logical instant "
                "(2026-05-17T11:00:00Z). Wall-clock spacing requires a live run."
            ),
            "generated_by": "data/build_run_data.py",
        },
        "procedure": {
            "name": "2-BM focus alignment (depth-of-focus phantom)",
            "kind": "focus_alignment",
            "events": _PROCEDURE_EVENTS,
            "event_count": len(_PROCEDURE_EVENTS),
            "iteration_count": len(_ITERATIONS),
            "activity_count": len(activities),
        },
        "iterations": iterations,
        "activities": activities,
    }


def main() -> None:
    out = Path(__file__).parent / "focus_run.json"
    data = _build()
    out.write_text(json.dumps(data, indent=2) + "\n")
    n_act = data["procedure"]["activity_count"]
    n_it = data["procedure"]["iteration_count"]
    verdicts = [it["converged"] for it in data["iterations"]]
    print(f"wrote {out} : {n_act} activities, {n_it} iterations, verdicts={verdicts}")


if __name__ == "__main__":
    main()

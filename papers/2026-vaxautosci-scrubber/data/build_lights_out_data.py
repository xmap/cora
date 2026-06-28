#!/usr/bin/env python3
"""Build the figure data for the lights-out supervised-alignment run.

Emits lights_out_run.json: one autonomous run combining a conducted
rotation-axis centering alignment (a 4-iteration peak-bracket search that
converges), a science scan whose third projection is in flight when the beam
drops, the RunSupervisor agent's hold, auto-resume, and fly-scan restart, and
completion. This is the run the paper's figures are drawn from.

Provenance. Values mirror the passing integration scenario

    apps/api/tests/integration/scenarios/test_2bm_lights_out_supervised_alignment.py

which produces exactly these activities, iteration verdicts, run-lifecycle
events, and the supervisor Resume Decision against a real Kernel + Postgres.
Run with the standard library only (no database). Timestamps are staggered
synthetically for a readable axis (the scenario records one logical instant);
the overnight wall-clock spread is illustrative.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

_BASE = datetime(2026, 5, 19, 1, 0, 0, tzinfo=UTC)


def _iso(t: datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def _at(seconds: float) -> str:
    return _iso(_BASE + timedelta(seconds=seconds))


# Per-iteration centering search on SampleTop_X (minimize COR residual, px).
_ITERATIONS = [
    {"index": 1, "target_mm": 0.000, "role": "initial", "residual": 2.00,
     "converged": False, "reason": "initial residual 2.00 px; minimum not yet bracketed"},
    {"index": 2, "target_mm": 0.040, "role": "step_positive", "residual": 1.05, "direction": "better",
     "converged": False, "reason": "residual improving (1.05 px); minimum not yet bracketed"},
    {"index": 3, "target_mm": 0.080, "role": "step_positive", "residual": 1.40, "direction": "worse",
     "converged": False, "reason": "residual rose to 1.40 px; minimum bracketed in [0.040, 0.080] mm"},
    {"index": 4, "target_mm": 0.060, "role": "bisect", "residual": 0.30, "direction": "minimum",
     "passed": True, "converged": True, "reason": None},
]

_PROCEDURE_EVENTS = [
    "ProcedureRegistered", "ProcedureStarted",
    "ProcedureIterationStarted", "ProcedureActivitiesLogbookOpened", "ProcedureIterationEnded",
    "ProcedureIterationStarted", "ProcedureIterationEnded",
    "ProcedureIterationStarted", "ProcedureIterationEnded",
    "ProcedureIterationStarted", "ProcedureIterationEnded",
    "ProcedureCompleted",
]

# Wall-clock anchors (synthetic): alignment runs ~a minute; the scan begins and
# the beam drops during the third projection; later it returns; resume; restart.
# Axis times are synthetic and compressed for a readable single axis; the
# overnight wall-clock spread (the hold can last tens of minutes) lives in the
# prose, not the axis.
_ITER_STRIDE = 12.0        # one acquire every 12 s; the whole axis is a 12 s grid
_BEAM_LOSS = 102.0         # RunHeld: the beam drops during the third projection
_BEAM_BACK = 150.0         # RunResumed (beam returns) after a 5-stride hold
_SAVE_AT = 210.0           # write the dataset one stride after the last projection
_RUN_DONE = 216.0          # run completes right after the save


def _build() -> dict:
    activities: list[dict] = []
    iterations: list[dict] = []
    seq = 0

    for spec in _ITERATIONS:
        i = spec["index"]
        start = (i - 1) * _ITER_STRIDE
        iterations.append({
            "iteration_index": i,
            "started_at": _at(start),
            "ended_at": _at(start + 10.0),
            "converged": spec["converged"],
            "reason": spec["reason"],
        })
        setpoint_payload = {
            "channel": "SampleTop_X", "target_value": spec["target_mm"],
            "units": "mm", "role": spec["role"],
        }
        if i == 1:
            setpoint_payload["note"] = "user-supplied start"
        check_payload = {
            "channel": "cor_residual", "passed": spec.get("passed", False),
            "source": "tomopy.recon.rotation", "actual": spec["residual"], "units": "px",
        }
        if "direction" in spec:
            check_payload["direction"] = spec["direction"]
        for kind, payload, at in (
            ("setpoint", setpoint_payload, start + 2.0),
            ("action", {"action_name": "acquire_frame", "params": {"exposure_ms": 100, "purpose": "alignment"}}, start + 6.0),
            ("check", check_payload, start + 9.0),
        ):
            seq += 1
            activities.append({
                "seq": seq, "iteration": i, "step_kind": kind,
                "payload": payload, "sampled_at": _at(at), "result": None,
            })

    # Lock at the converged center and command the fly-scan rotation.
    seq += 1
    activities.append({
        "seq": seq, "iteration": None, "step_kind": "setpoint",
        "payload": {"channel": "SampleTop_X", "target_value": 0.060, "units": "mm", "role": "lock_at_center"},
        "sampled_at": _at(46.0), "result": None,
    })
    seq += 1
    activities.append({
        "seq": seq, "iteration": None, "step_kind": "setpoint",
        "payload": {"channel": "rotation_angle", "target_value": 180.0, "units": "deg",
                    "role": "fly_scan", "note": "continuous 0->180 deg sweep"},
        "sampled_at": _at(50.0), "result": None,
    })

    def _proj(index: int, angle: float, at: float, result: str) -> None:
        nonlocal seq
        seq += 1
        activities.append({
            "seq": seq, "iteration": None, "step_kind": "action",
            "payload": {"action_name": "acquire_projection",
                        "params": {"exposure_ms": 100, "angle_deg": angle, "index": index},
                        "result": result},
            "sampled_at": _at(at), "result": result,
        })

    def _taxi_prep(taxi_at: float, prep_at: float) -> None:
        nonlocal seq
        seq += 1
        activities.append({
            "seq": seq, "iteration": None, "step_kind": "setpoint",
            "payload": {"channel": "rotation_angle", "target_value": -5.0, "units": "deg",
                        "role": "taxi", "note": "run-up to constant velocity"},
            "sampled_at": _at(taxi_at), "result": None,
        })
        seq += 1
        activities.append({
            "seq": seq, "iteration": None, "step_kind": "action",
            "payload": {"action_name": "fly_scan_prep", "params": {"rearm_pso": True}, "result": "ok"},
            "sampled_at": _at(prep_at), "result": "ok",
        })

    # Fly-scan taxi + PSO arm before the first frame, then the scan on the 12 s
    # grid: two projections complete and the third is in flight when the beam
    # drops at 102 s.
    _taxi_prep(54.0, 58.0)
    _proj(1, 0.0, 66.0, "ok")
    _proj(2, 30.0, 78.0, "ok")
    _proj(3, 60.0, 90.0, "in_flight")

    # After the hold the fly-scan is restarted (taxi back to constant velocity,
    # re-arm the PSO) before the interrupted third projection is re-acquired and
    # the scan finishes.
    _taxi_prep(154.0, 158.0)
    _proj(3, 60.0, 162.0, "ok")
    _proj(4, 90.0, 174.0, "ok")
    _proj(5, 120.0, 186.0, "ok")
    _proj(6, 150.0, 198.0, "ok")

    # Save the collected scan to disk: the data-collection run ends here.
    seq += 1
    activities.append({
        "seq": seq, "iteration": None, "step_kind": "action",
        "payload": {"action_name": "write_dataset",
                    "params": {"format": "dxfile-hdf5", "projections": 6}, "result": "ok"},
        "sampled_at": _at(_SAVE_AT), "result": "ok",
    })

    run_events = [
        {"type": "RunStarted", "at": _at(0.0), "by": "operator", "role": "human"},
        {"type": "RunHeld", "at": _at(_BEAM_LOSS), "by": "RunSupervisor", "role": "agent",
         "decision": {"context": "RunSupervision", "choice": "Hold"}},
        {"type": "RunResumed", "at": _at(_BEAM_BACK), "by": "RunSupervisor", "role": "agent",
         "decision": {"context": "RunSupervision", "choice": "Resume"}},
        {"type": "RunCompleted", "at": _at(_RUN_DONE), "by": "operator", "role": "human"},
    ]

    return {
        "provenance": {
            "source": (
                "Values mirror the passing integration scenario "
                "apps/api/tests/integration/scenarios/"
                "test_2bm_lights_out_supervised_alignment.py, which produces these "
                "activities, iteration verdicts, run-lifecycle events, and the "
                "supervisor Resume Decision against a real Kernel + Postgres."
            ),
            "run": (
                "Lights-out, agent-supervised run at APS 2-BM: conducted rotation-axis "
                "centering alignment, the science scan's third projection interrupted "
                "by beam loss, RunSupervisor hold + auto-resume + fly-scan restart, "
                "then the scan continues to completion."
            ),
            "timestamps": (
                "sampled_at / event times staggered synthetically for a readable axis; "
                "the scenario records one logical instant. Overnight spread is illustrative."
            ),
            "cursor_at": _at(_BEAM_LOSS),
            "beam_loss_at": _at(_BEAM_LOSS),
            "beam_back_at": _at(_BEAM_BACK),
            "generated_by": "data/build_lights_out_data.py",
        },
        "run": {
            "name": "2-BM lights-out tomography (pre-scan align + science scan)",
            "supervisor_agent": "RunSupervisor (deterministic)",
            "events": run_events,
        },
        "procedure": {
            "name": "2-BM rotation-axis centering (pre-scan alignment)",
            "kind": "alignment",
            "phase_of_run": True,
            "events": _PROCEDURE_EVENTS,
            "iteration_count": len(_ITERATIONS),
        },
        "iterations": iterations,
        "activities": activities,
    }


def main() -> None:
    out = Path(__file__).parent / "lights_out_run.json"
    data = _build()
    out.write_text(json.dumps(data, indent=2) + "\n")
    verdicts = [it["converged"] for it in data["iterations"]]
    print(
        f"wrote {out} : {len(data['activities'])} activities, "
        f"{len(data['iterations'])} iterations verdicts={verdicts}, "
        f"run={[e['type'] for e in data['run']['events']]}"
    )


if __name__ == "__main__":
    main()

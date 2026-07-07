#!/usr/bin/env python3
"""Build the figure data for the robot-loaded, lights-out tomography run.

Emits lights_out_run.json: one autonomous overnight session in which a
sample-changing robot loads two samples in turn. For each sample the system
mounts it, conducts a rotation-axis centering alignment (a 4-iteration
peak-bracket search that converges), runs the science scan, then dismounts it.
On the second sample the beam drops while the third projection is in flight; the
RunSupervisor agent holds the run, auto-resumes when the beam returns, and the
fly-scan restarts. This is the run the paper's figures are drawn from.

Provenance. Values mirror the passing integration scenario

    apps/api/tests/integration/scenarios/test_2bm_robot_lights_out_two_sample.py

which produces these activities, iteration verdicts, run-lifecycle events, the
robot mount/dismount custody events, and the supervisor Resume Decision against
a real Kernel + Postgres. Run with the standard library only (no database).
Timestamps are staggered synthetically for a readable axis (the scenario records
one logical instant); the overnight wall-clock spread is illustrative.

Scope (modeled vs. deployed). The sample-change hardware at 2-BM (a UR3e arm
with its own EPICS control) is deployed and has executed mount/dismount cycles
with a beamline handshake; tomoscan is PV-scriptable. CORA's orchestration of
the robot, and the supervisor decision layer (FOV-fit and lens-change branches,
per-sample recentering verdicts), are modeled here rather than deployed, and are
played through the same real Kernel + Postgres event store as the rest of the
run. See the paper's Limitations section.
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


# Two samples the robot loads in turn. Sample A converges to a different center
# than sample B: the per-sample recentering finds each sample's own position
# relative to the fixed rotation axis. Sample B carries the canonical numbers the
# paper walks through, and the beam-loss / hold lands on its scan.
_SAMPLE_A_ITERATIONS = [
    {"index": 1, "target_mm": 0.000, "role": "initial", "residual": 1.80,
     "converged": False, "reason": "initial residual 1.80 px; minimum not yet bracketed"},
    {"index": 2, "target_mm": 0.030, "role": "step_positive", "residual": 0.90, "direction": "better",
     "converged": False, "reason": "residual improving (0.90 px); minimum not yet bracketed"},
    {"index": 3, "target_mm": 0.060, "role": "step_positive", "residual": 1.15, "direction": "worse",
     "converged": False, "reason": "residual rose to 1.15 px; minimum bracketed in [0.030, 0.060] mm"},
    {"index": 4, "target_mm": 0.045, "role": "bisect", "residual": 0.25, "direction": "minimum",
     "passed": True, "converged": True, "reason": None},
]

_SAMPLE_B_ITERATIONS = [
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

# Synthetic wall-clock grid. Two per-sample blocks laid on one axis; the beam
# drops during sample B's scan. Axis times are compressed for a readable single
# axis (the overnight spread, and the tens-of-minutes hold, live in the prose).
_ROBOT = "Manipulator (UR3e sample changer)"
_ITER_LEN = 8.0            # one align iteration block: setpoint, acquire, check
_ALIGN_STRIDE = 8.0
_SCAN_STRIDE = 4.0         # one projection every 4 s within a scan


def _sample_block(
    *,
    sample: int,
    subject: str,
    base: float,
    iterations_spec: list[dict],
    beam_loss: bool,
    seq_start: int,
) -> dict:
    """Build one sample's activities, iterations, and lane anchors.

    Layout within the block (offsets from `base`):
      robot mount at 0; run starts at 4; alignment iterations from 8;
      lock + fly-scan setup; the science scan; (for the beam-loss sample) a
      hold + resume + restart; the dataset write; robot dismount.
    Returns the block's activities/iterations plus the timing anchors the
    renderer needs (custody band, robot events, run events, scan markers).
    """
    activities: list[dict] = []
    iterations: list[dict] = []
    seq = seq_start

    mount_at = base + 0.0
    custody_start = base + 3.0
    run_started = base + 4.0
    align_base = base + 8.0

    for spec in iterations_spec:
        i = spec["index"]
        start = align_base + (i - 1) * _ALIGN_STRIDE
        iterations.append({
            "sample": sample,
            "iteration_index": i,
            "started_at": _at(start),
            "ended_at": _at(start + 7.0),
            "converged": spec["converged"],
            "reason": spec["reason"],
        })
        setpoint_payload = {
            "channel": "SampleTop_X", "target_value": spec["target_mm"],
            "units": "mm", "role": spec["role"],
        }
        if i == 1:
            setpoint_payload["note"] = "recenter after mount"
        check_payload = {
            "channel": "cor_residual", "passed": spec.get("passed", False),
            "source": "tomopy.recon.rotation", "actual": spec["residual"], "units": "px",
        }
        if "direction" in spec:
            check_payload["direction"] = spec["direction"]
        for kind, payload, at in (
            ("setpoint", setpoint_payload, start + 2.0),
            ("action", {"action_name": "acquire_frame",
                        "params": {"exposure_ms": 100, "purpose": "alignment"}}, start + 4.0),
            ("check", check_payload, start + 6.0),
        ):
            seq += 1
            activities.append({
                "seq": seq, "sample": sample, "iteration": i, "step_kind": kind,
                "payload": payload, "sampled_at": _at(at), "result": None,
            })

    align_end = align_base + len(iterations_spec) * _ALIGN_STRIDE

    def _act(step_kind: str, payload: dict, at: float, result: str | None) -> None:
        nonlocal seq
        seq += 1
        activities.append({
            "seq": seq, "sample": sample, "iteration": None, "step_kind": step_kind,
            "payload": payload, "sampled_at": _at(at), "result": result,
        })

    converged_center = iterations_spec[-1]["target_mm"]
    _act("setpoint",
         {"channel": "SampleTop_X", "target_value": converged_center, "units": "mm",
          "role": "lock_at_center"}, align_end + 2.0, None)
    _act("setpoint",
         {"channel": "rotation_angle", "target_value": 180.0, "units": "deg",
          "role": "fly_scan", "note": "continuous 0->180 deg sweep"}, align_end + 4.0, None)

    scan_base = align_end + 6.0

    def _taxi_prep(taxi_at: float, prep_at: float) -> None:
        _act("setpoint",
             {"channel": "rotation_angle", "target_value": -5.0, "units": "deg",
              "role": "taxi", "note": "run-up to constant velocity"}, taxi_at, None)
        _act("action",
             {"action_name": "fly_scan_prep", "params": {"rearm_pso": True}, "result": "ok"},
             prep_at, "ok")

    def _proj(index: int, angle: float, at: float, result: str) -> None:
        _act("action",
             {"action_name": "acquire_projection",
              "params": {"exposure_ms": 100, "angle_deg": angle, "index": index},
              "result": result}, at, result)

    _taxi_prep(scan_base, scan_base + 2.0)
    proj_base = scan_base + 4.0

    beam_loss_at: float | None = None
    beam_back_at: float | None = None
    run_events: list[dict]

    if not beam_loss:
        # Clean sample: three projections, all good, then the dataset write.
        _proj(1, 0.0, proj_base, "ok")
        _proj(2, 90.0, proj_base + _SCAN_STRIDE, "ok")
        _proj(3, 180.0, proj_base + 2 * _SCAN_STRIDE, "ok")
        save_at = proj_base + 2 * _SCAN_STRIDE + _SCAN_STRIDE
        _act("action",
             {"action_name": "write_dataset",
              "params": {"format": "dxfile-hdf5", "projections": 3}, "result": "ok"},
             save_at, "ok")
        custody_end = save_at + 2.0
        dismount_at = custody_end + 1.0
        run_done = save_at + 1.0
        run_events = [
            {"type": "RunStarted", "at": _at(run_started), "by": "operator", "role": "human"},
            {"type": "RunCompleted", "at": _at(run_done), "by": "operator", "role": "human"},
        ]
    else:
        # Beam-loss sample: two projections complete, the third is in flight when
        # the beam drops; the supervisor holds, then resumes; the fly-scan
        # restarts and the scan runs to completion.
        _proj(1, 0.0, proj_base, "ok")
        _proj(2, 30.0, proj_base + _SCAN_STRIDE, "ok")
        _proj(3, 60.0, proj_base + 2 * _SCAN_STRIDE, "in_flight")
        beam_loss_at = proj_base + 2 * _SCAN_STRIDE + 2.0
        beam_back_at = beam_loss_at + 20.0
        _taxi_prep(beam_back_at + 2.0, beam_back_at + 4.0)
        restart_base = beam_back_at + 6.0
        _proj(3, 60.0, restart_base, "ok")
        _proj(4, 90.0, restart_base + _SCAN_STRIDE, "ok")
        _proj(5, 120.0, restart_base + 2 * _SCAN_STRIDE, "ok")
        _proj(6, 150.0, restart_base + 3 * _SCAN_STRIDE, "ok")
        save_at = restart_base + 3 * _SCAN_STRIDE + _SCAN_STRIDE
        _act("action",
             {"action_name": "write_dataset",
              "params": {"format": "dxfile-hdf5", "projections": 6}, "result": "ok"},
             save_at, "ok")
        custody_end = save_at + 2.0
        dismount_at = custody_end + 1.0
        run_done = save_at + 1.0
        run_events = [
            {"type": "RunStarted", "at": _at(run_started), "by": "operator", "role": "human"},
            {"type": "RunHeld", "at": _at(beam_loss_at), "by": "RunSupervisor", "role": "agent",
             "decision": {"context": "RunSupervision", "choice": "Hold"}},
            {"type": "RunResumed", "at": _at(beam_back_at), "by": "RunSupervisor", "role": "agent",
             "decision": {"context": "RunSupervision", "choice": "Resume"}},
            {"type": "RunCompleted", "at": _at(run_done), "by": "operator", "role": "human"},
        ]

    return {
        "sample": sample,
        "subject": subject,
        "custody": {"mount_at": _at(custody_start), "dismount_at": _at(custody_end)},
        "robot_events": [
            {"action": "mount", "subject": subject, "at": _at(mount_at)},
            {"action": "dismount", "subject": subject, "at": _at(dismount_at)},
        ],
        "run": {
            "index": sample,
            "subject": subject,
            "events": run_events,
        },
        "iterations": iterations,
        "activities": activities,
        "beam_loss_at": _at(beam_loss_at) if beam_loss_at is not None else None,
        "beam_back_at": _at(beam_back_at) if beam_back_at is not None else None,
        "seq_end": seq,
    }


def _build() -> dict:
    a = _sample_block(
        sample=1, subject="sample A (porous sandstone core)", base=0.0,
        iterations_spec=_SAMPLE_A_ITERATIONS, beam_loss=False, seq_start=0,
    )
    b = _sample_block(
        sample=2, subject="sample B (porous sandstone core)", base=72.0,
        iterations_spec=_SAMPLE_B_ITERATIONS, beam_loss=True, seq_start=a["seq_end"],
    )

    activities = a["activities"] + b["activities"]
    iterations = a["iterations"] + b["iterations"]
    robot_events = a["robot_events"] + b["robot_events"]
    samples = [
        {"index": a["sample"], "subject": a["subject"], **a["custody"]},
        {"index": b["sample"], "subject": b["subject"], **b["custody"]},
    ]
    runs = [a["run"], b["run"]]

    beam_loss_at = b["beam_loss_at"]
    beam_back_at = b["beam_back_at"]

    return {
        "provenance": {
            "source": (
                "Values mirror the passing integration scenario "
                "apps/api/tests/integration/scenarios/"
                "test_2bm_robot_lights_out_two_sample.py, which produces these "
                "activities, iteration verdicts, run-lifecycle events, robot "
                "mount/dismount custody events, and the supervisor Resume Decision "
                "against a real Kernel + Postgres."
            ),
            "run": (
                "Robot-loaded, lights-out session at APS 2-BM: a sample-changing "
                "robot loads two samples in turn; each is recentered and scanned; "
                "the beam drops during the second sample's scan, and the "
                "RunSupervisor holds + auto-resumes + restarts the fly-scan."
            ),
            "scope": (
                "The sample-change hardware and its EPICS control are deployed and "
                "have run; CORA's orchestration of the robot and the supervisor "
                "decision layer are modeled here, played through the real event "
                "store. See the paper's Limitations section."
            ),
            "timestamps": (
                "sampled_at / event times staggered synthetically for a readable "
                "axis; the scenario records one logical instant. Overnight spread "
                "and the tens-of-minutes hold are illustrative."
            ),
            "cursor_at": beam_loss_at,
            "beam_loss_at": beam_loss_at,
            "beam_back_at": beam_back_at,
            "generated_by": "data/build_lights_out_data.py",
        },
        "robot": {
            "asset": _ROBOT,
            "role": "Positioner (Manipulator family); loads/unloads the sample Subject",
            "events": robot_events,
        },
        "samples": samples,
        "runs": runs,
        "procedure": {
            "name": "2-BM rotation-axis centering (pre-scan alignment)",
            "kind": "alignment",
            "phase_of_run": True,
            "events": _PROCEDURE_EVENTS,
            "per_sample": True,
        },
        "iterations": iterations,
        "activities": activities,
    }


def main() -> None:
    out = Path(__file__).parent / "lights_out_run.json"
    data = _build()
    out.write_text(json.dumps(data, indent=2) + "\n")
    n_samples = len(data["samples"])
    n_runs = len(data["runs"])
    print(
        f"wrote {out} : {n_samples} samples, {n_runs} runs, "
        f"{len(data['activities'])} activities, {len(data['iterations'])} iterations, "
        f"robot events={[e['action'] for e in data['robot']['events']]}"
    )


if __name__ == "__main__":
    main()

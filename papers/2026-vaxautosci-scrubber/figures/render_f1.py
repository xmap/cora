#!/usr/bin/env python3
"""Render Figure 1, the replay scrubber, from data/lights_out_run.json.

Static rendering of the interactive scrubber over one lights-out, agent-
supervised run: a run-lifecycle / who-drove-it lane (operator vs RunSupervisor),
per-iteration convergence brackets colored by verdict (the rotation-axis
centering search), activity swim-lanes, a shaded held band, and a fold-to-
version cursor parked at the beam-loss instant, where the first projection is an
open interval (in flight, no outcome yet).

Run: uv run --no-project --with matplotlib python figures/render_f1.py
Output: figures/f1_scrubber.pdf (and .png).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

HERE = Path(__file__).parent
DATA = json.loads((HERE.parent / "data" / "lights_out_run.json").read_text())

LANE_Y = {"setpoint": 2, "action": 1, "check": 0}
LANE_LABEL = {2: "Setpoint", 1: "Acquire", 0: "Check"}
LANE_COLOR = {"setpoint": "#3B6EA5", "action": "#6B7280", "check": "#2A9D8F"}
LANE_MARKER = {"setpoint": "s", "action": "^", "check": "o"}
C_HUMAN = "#3B6EA5"     # operator
C_AGENT = "#C0392B"     # RunSupervisor
C_OPEN = "#D9A441"      # not-converged bracket
C_CONV = "#2E7D32"      # converged bracket
C_CURSOR = "#C0392B"
Y_BRACKET = 3.0
Y_RUN = 3.85


def _parse(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    acts = DATA["activities"]
    iters = DATA["iterations"]
    run_events = DATA["run"]["events"]
    prov = DATA["provenance"]
    t0 = _parse(run_events[0]["at"])

    def secs(s: str) -> float:
        return (_parse(s) - t0).total_seconds()

    cursor = secs(prov["cursor_at"])
    beam_loss = secs(prov["beam_loss_at"])
    beam_back = secs(prov["beam_back_at"])
    xmax = max(secs(e["at"]) for e in run_events)

    fig, ax = plt.subplots(figsize=(7.4, 3.6))

    # Held band: the whole run is held between beam loss and beam back.
    ax.axvspan(beam_loss, beam_back, color="#F0F0F0", zorder=0)
    ax.text((beam_loss + beam_back) / 2, Y_RUN + 0.34, "held", ha="center", va="bottom",
            fontsize=6.6, color="#888888", style="italic")

    # Run lifecycle / who-drove-it lane.
    for ev in run_events:
        x = secs(ev["at"])
        agent = ev["role"] == "agent"
        col = C_AGENT if agent else C_HUMAN
        ax.scatter([x], [Y_RUN], marker=("D" if agent else "s"), s=58, color=col,
                   edgecolors="white", linewidths=0.6, zorder=4)
        label = {"RunStarted": "started", "RunHeld": "held", "RunResumed": "resumed",
                 "RunCompleted": "completed"}[ev["type"]]
        who = "RunSupervisor" if agent else "operator"
        ax.annotate(f"{label}\n({who})", (x, Y_RUN), textcoords="offset points",
                    xytext=(0, 8), ha="center", fontsize=5.8, color=col, linespacing=0.9)

    # Convergence brackets, colored by verdict.
    for it in iters:
        a, b = secs(it["started_at"]), secs(it["ended_at"])
        col = C_CONV if it["converged"] else C_OPEN
        ax.plot([a, b], [Y_BRACKET, Y_BRACKET], color=col, lw=5, solid_capstyle="butt", alpha=0.9)
        for x in (a, b):
            ax.plot([x, x], [Y_BRACKET - 0.1, Y_BRACKET + 0.1], color=col, lw=1.6)
        verdict = "converged" if it["converged"] else "open"
        ax.text((a + b) / 2, Y_BRACKET + 0.16, f"i{it['iteration_index']}", ha="center",
                va="bottom", fontsize=6, color=col)
    ax.text(secs(iters[-1]["ended_at"]) + 2, Y_BRACKET, "centering converged", fontsize=6.2,
            va="center", ha="left", color=C_CONV)

    # Activity swim-lanes (alignment), plus the first science projection.
    for a in acts:
        if a["payload"].get("action_name") == "acquire_first_projection":
            continue
        x, y = secs(a["sampled_at"]), LANE_Y[a["step_kind"]]
        ax.scatter([x], [y], marker=LANE_MARKER[a["step_kind"]], s=52,
                   color=LANE_COLOR[a["step_kind"]], zorder=3, edgecolors="white", linewidths=0.5)
        if a["step_kind"] == "check":
            ax.annotate(f"{a['payload']['actual']:.2f}", (x, y), textcoords="offset points",
                        xytext=(0, -11), ha="center", fontsize=5.6, color=LANE_COLOR["check"])

    # First projection: in-flight from begin to the cursor (open), faint outcome after resume.
    proj = {a["result"]: secs(a["sampled_at"]) for a in acts
            if a["payload"].get("action_name") == "acquire_first_projection"}
    y = LANE_Y["action"]
    begin = proj["in_flight"]
    ax.plot([begin, cursor], [y, y], color=C_OPEN, lw=5, ls=(0, (4, 3)), alpha=0.9, zorder=2)
    ax.scatter([begin], [y], marker="D", s=46, color=C_OPEN, edgecolors="white", linewidths=0.5, zorder=3)
    ax.annotate("first projection: in flight", (begin, y), textcoords="offset points",
                xytext=(2, 9), ha="left", fontsize=5.8, color="#7a5a12")
    ax.scatter([proj["ok"]], [y], marker="^", s=46, color=LANE_COLOR["action"], alpha=0.4,
               edgecolors="white", linewidths=0.5, zorder=3)
    ax.annotate("completes\nafter resume", (proj["ok"], y), textcoords="offset points",
                xytext=(0, -16), ha="center", fontsize=5.4, color="#9aa0a6", linespacing=0.9)

    # Fold-to-version cursor at the beam-loss instant.
    ax.axvline(cursor, color=C_CURSOR, ls="--", lw=1.3, zorder=5)
    ax.text(cursor, Y_RUN + 0.66, "cursor:\nbeam loss", color=C_CURSOR, fontsize=6.6, ha="center",
            va="bottom", fontweight="bold", linespacing=0.9)

    readout = (
        "folded state at cursor\n"
        "alignment: converged (0.30 px)\n"
        "first projection: in flight,\n  no outcome\n"
        "run: held by RunSupervisor\n"
        "fidelity: verified"
    )
    ax.text(1.02, 0.5, readout, transform=ax.transAxes, fontsize=6.2, va="center", ha="left",
            bbox={"boxstyle": "round,pad=0.45", "fc": "#FCF3E6", "ec": C_CURSOR, "lw": 0.8})

    ax.set_yticks(list(LANE_LABEL))
    ax.set_yticklabels([LANE_LABEL[k] for k in LANE_LABEL], fontsize=8)
    ax.set_ylim(-0.9, Y_RUN + 1.05)
    ax.set_xlim(-4, xmax + 6)
    ax.set_xlabel("time (s; synthetic spacing, see data/README.md)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.set_title("Replay scrubber: a lights-out, agent-supervised run at APS 2-BM",
                 fontsize=9.5, loc="left")

    legend = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor=C_HUMAN, markersize=7, label="operator"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=C_AGENT, markersize=7, label="RunSupervisor"),
        Line2D([0], [0], color=C_OPEN, lw=4, label="bracket: open"),
        Line2D([0], [0], color=C_CONV, lw=4, label="bracket: converged"),
        Line2D([0], [0], color=C_OPEN, lw=3, ls=(0, (4, 3)), label="in-flight (open)"),
    ]
    ax.legend(handles=legend, loc="lower left", ncol=5, fontsize=6.2, frameon=False,
              bbox_to_anchor=(0.0, -0.30))

    for ext in ("pdf", "png"):
        out = HERE / f"f1_scrubber.{ext}"
        fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.12)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()

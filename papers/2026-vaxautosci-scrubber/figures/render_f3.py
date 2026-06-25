#!/usr/bin/env python3
"""Render Figure 3, crash recovery, from data/crash_run.json.

A conducted run where each side-effecting setpoint records a pre-effect
in-flight marker (diamond) before its outcome (circle); a completed step joins
the two with a solid bar. The run is truncated after the final marker, so that
step is an open interval (dashed, no outcome): the interrupted step the scrubber
localizes by step_index.

Run: uv run --no-project --with matplotlib python figures/render_f3.py
Output: figures/f3_crash.pdf (and .png).
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
DATA = json.loads((HERE.parent / "data" / "crash_run.json").read_text())

LANE_Y = {"setpoint": 1, "check": 0}
LANE_LABEL = {1: "Setpoint", 0: "Check"}
C_MARK = "#3B6EA5"     # in-flight marker (intent)
C_OK = "#2E7D32"       # outcome (ok)
C_CHECK = "#2A9D8F"    # check
C_OPEN = "#C0392B"     # interrupted / open interval


def _parse(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    acts = DATA["activities"]
    interrupted = DATA["procedure"]["interrupted_step_index"]
    t0 = _parse(acts[0]["sampled_at"])

    def secs(s: str) -> float:
        return (_parse(s) - t0).total_seconds()

    markers = {a["step_index"]: secs(a["sampled_at"]) for a in acts if a["step_kind"] == "setpoint" and a["result"] == "in_flight"}
    outcomes = {a["step_index"]: (secs(a["sampled_at"]), a) for a in acts if a["step_kind"] == "setpoint" and a["result"] == "ok"}
    checks = [(a["step_index"], secs(a["sampled_at"]), a) for a in acts if a["step_kind"] == "check"]

    last_complete_t = max([t for t, _ in outcomes.values()] + [t for _, t, _ in checks])
    open_end = max(markers.values()) + 7.0

    fig, ax = plt.subplots(figsize=(5.4, 2.5))

    # Setpoint lane: completed steps (marker -> outcome) and the interrupted one.
    for si, tm in sorted(markers.items()):
        y = LANE_Y["setpoint"]
        if si in outcomes:
            to, row = outcomes[si]
            ax.plot([tm, to], [y, y], color=C_OK, lw=6, solid_capstyle="butt", alpha=0.45, zorder=1)
            ax.scatter([tm], [y], marker="D", s=46, color=C_MARK, edgecolors="white", linewidths=0.6, zorder=3)
            ax.scatter([to], [y], marker="o", s=60, color=C_OK, edgecolors="white", linewidths=0.6, zorder=3)
            ax.annotate(
                f"{row['payload']['address']} = {row['payload']['value']}  (ok)", (tm, y),
                textcoords="offset points", xytext=(0, 9), ha="left", fontsize=6.6, color=C_OK,
            )
        else:
            # Interrupted: marker with no outcome -> open interval.
            ax.plot([tm, open_end], [y, y], color=C_OPEN, lw=5, ls=(0, (4, 3)), alpha=0.8, zorder=1)
            ax.scatter([tm], [y], marker="D", s=52, color=C_OPEN, edgecolors="white", linewidths=0.6, zorder=3)
            ax.annotate("", xy=(open_end + 0.4, y), xytext=(open_end - 1.4, y),
                        arrowprops={"arrowstyle": "-|>", "color": C_OPEN, "lw": 1.4})
            dang = next(a for a in acts if a["step_index"] == si and a["result"] == "in_flight")
            ax.annotate(
                f"{dang['payload']['address']} = {dang['payload']['value']}", (tm, y),
                textcoords="offset points", xytext=(0, 9), ha="left", fontsize=6.6, color=C_OPEN,
            )
            ax.annotate(
                f"in-flight, no outcome:  interrupted step (step_index {si})",
                ((tm + open_end) / 2, y), textcoords="offset points", xytext=(0, -15),
                ha="center", fontsize=6.6, color=C_OPEN, fontweight="bold",
            )

    # Check lane.
    for _si, tc, _row in checks:
        ax.scatter([tc], [LANE_Y["check"]], marker="o", s=60, color=C_CHECK, edgecolors="white", linewidths=0.6, zorder=3)
        ax.annotate("check (ok)", (tc, LANE_Y["check"]), textcoords="offset points", xytext=(0, -13), ha="center", fontsize=6.6, color=C_CHECK)

    # Crash line, just after the dangling marker.
    crash_t = max(markers.values()) + 1.6
    ax.axvline(crash_t, color=C_OPEN, ls="--", lw=1.2, zorder=2)
    ax.text(crash_t, 1.62, "crash", color=C_OPEN, fontsize=7.5, ha="center", fontweight="bold")

    # "Last complete state" marker at the last finished step.
    ax.annotate(
        "last complete state", (last_complete_t, LANE_Y["check"]),
        textcoords="offset points", xytext=(0, 16), ha="center", fontsize=6.2, color="#555555",
    )
    ax.axvline(last_complete_t, color="#999999", ls=":", lw=0.9, zorder=1)

    ax.set_yticks(list(LANE_LABEL))
    ax.set_yticklabels([LANE_LABEL[y] for y in LANE_LABEL], fontsize=8)
    ax.set_ylim(-0.9, 1.95)
    ax.set_xlim(-1.5, open_end + 2)
    ax.set_xlabel("time (s; spacing synthetic)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_title("Crash recovery: an interrupted conducted step", fontsize=9, loc="left")

    legend = [
        Line2D([0], [0], marker="D", color="w", markerfacecolor=C_MARK, markersize=6, label="in-flight marker"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=C_OK, markersize=6, label="outcome"),
        Line2D([0], [0], color=C_OPEN, lw=3, ls=(0, (4, 3)), label="interrupted (open)"),
    ]
    ax.legend(handles=legend, loc="lower left", ncol=3, fontsize=6.4, frameon=False, bbox_to_anchor=(0.0, -0.42))

    for ext in ("pdf", "png"):
        out = HERE / f"f3_crash.{ext}"
        fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.12)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()

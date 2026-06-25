#!/usr/bin/env python3
"""Render Figure 1, the replay scrubber, from data/focus_run.json.

Static rendering of the interactive scrubber at one cursor position: activity
swim-lanes (setpoint / acquire / check), per-iteration convergence brackets
colored by verdict (the peak-bracket search), and a fold-to-version cursor with
the folded-state read-out. The clean focus run has no in-flight steps, so no
open intervals appear here; those are exercised by Figure 3 (the crash case).

Run: uv run --no-project --with matplotlib python figures/render_f1.py
Output: figures/f1_scrubber.pdf (and .png for quick viewing).
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
DATA = json.loads((HERE.parent / "data" / "focus_run.json").read_text())

LANE_Y = {"setpoint": 2, "action": 1, "check": 0}
LANE_LABEL = {2: "Setpoint", 1: "Acquire", 0: "Check"}
LANE_COLOR = {"setpoint": "#3B6EA5", "action": "#6B7280", "check": "#2A9D8F"}
LANE_MARKER = {"setpoint": "s", "action": "^", "check": "o"}
C_OPEN = "#D9A441"      # not-converged bracket (amber)
C_CONV = "#2E7D32"      # converged bracket (green)
C_CURSOR = "#C0392B"    # cursor (crimson)
Y_BRACKET = 3.25


def _parse(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    acts = DATA["activities"]
    iters = DATA["iterations"]
    t0 = _parse(acts[0]["sampled_at"])

    def secs(s: str) -> float:
        return (_parse(s) - t0).total_seconds()

    xmax = max(secs(a["sampled_at"]) for a in acts)

    fig, ax = plt.subplots(figsize=(7.2, 3.1))

    # Per-iteration convergence brackets (peak-bracket search), colored by verdict.
    for it in iters:
        a, b = secs(it["started_at"]), secs(it["ended_at"])
        col = C_CONV if it["converged"] else C_OPEN
        ax.plot([a, b], [Y_BRACKET, Y_BRACKET], color=col, lw=5, solid_capstyle="butt", alpha=0.9)
        for x in (a, b):
            ax.plot([x, x], [Y_BRACKET - 0.13, Y_BRACKET + 0.13], color=col, lw=1.8)
        verdict = "converged" if it["converged"] else "open"
        ax.text(
            (a + b) / 2, Y_BRACKET + 0.22, f"iter {it['iteration_index']} ({verdict})",
            ha="center", va="bottom", fontsize=7, color=col,
        )

    # Annotate the narrowing position bracket on the bracketing/bisect passes.
    def _iter_check_x(idx: int) -> float:
        return next(secs(a["sampled_at"]) for a in acts if a["iteration"] == idx and a["step_kind"] == "check")

    ax.annotate(
        "bracket [0.500, 1.000] mm", (_iter_check_x(3), Y_BRACKET),
        textcoords="offset points", xytext=(0, -16), ha="center", fontsize=6.3, color="#7a5a12",
    )
    ax.annotate(
        "bisect to 0.750 mm", (_iter_check_x(4), Y_BRACKET),
        textcoords="offset points", xytext=(0, -16), ha="center", fontsize=6.3, color="#1b5e20",
    )

    # Activity markers in their swim-lanes.
    for a in acts:
        x, y = secs(a["sampled_at"]), LANE_Y[a["step_kind"]]
        ax.scatter(
            [x], [y], marker=LANE_MARKER[a["step_kind"]], s=66,
            color=LANE_COLOR[a["step_kind"]], zorder=3, edgecolors="white", linewidths=0.6,
        )
        if a["step_kind"] == "setpoint":
            ax.annotate(
                f"{a['payload']['target_value']:.3f}", (x, y),
                textcoords="offset points", xytext=(0, 7), ha="center", fontsize=6, color=LANE_COLOR["setpoint"],
            )
        elif a["step_kind"] == "check":
            ax.annotate(
                f"s={a['payload']['actual']:.2f}", (x, y),
                textcoords="offset points", xytext=(0, -12), ha="center", fontsize=6, color=LANE_COLOR["check"],
            )

    # Fold-to-version cursor at iteration 3's check: peak just bracketed.
    cur = _iter_check_x(3)
    ax.axvline(cur, color=C_CURSOR, ls="--", lw=1.3, zorder=4)
    ax.text(cur, Y_BRACKET + 0.55, "cursor", color=C_CURSOR, fontsize=7.5, ha="center", fontweight="bold")

    readout = (
        "folded state at cursor\n"
        "pass 3 of 4\n"
        "Z = 1.000 mm,  sharpness 0.65\n"
        "bracket [0.500, 1.000] mm\n"
        "verdict: not converged\n"
        "fidelity: verified"
    )
    # Anchored in the reserved right margin (outside the axes) so it never
    # covers the iteration-4 and finalize markers; bbox_inches="tight" grows
    # the canvas to include it.
    ax.text(
        1.02, 0.5, readout, transform=ax.transAxes, fontsize=6.6, va="center", ha="left",
        bbox={"boxstyle": "round,pad=0.45", "fc": "#FCF3E6", "ec": C_CURSOR, "lw": 0.8},
    )

    ax.set_yticks(list(LANE_LABEL))
    ax.set_yticklabels([LANE_LABEL[y] for y in LANE_LABEL], fontsize=8)
    ax.set_ylim(-0.8, 4.15)
    ax.set_xlim(-3, xmax + 5)
    ax.set_xlabel("time (s; spacing synthetic, see data/README.md)", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_title("Replay scrubber: APS 2-BM autofocus alignment", fontsize=9.5, loc="left")

    legend = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor=LANE_COLOR["setpoint"], markersize=7, label="setpoint"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=LANE_COLOR["action"], markersize=7, label="acquire"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=LANE_COLOR["check"], markersize=7, label="check"),
        Line2D([0], [0], color=C_OPEN, lw=4, label="bracket: open"),
        Line2D([0], [0], color=C_CONV, lw=4, label="bracket: converged"),
    ]
    ax.legend(handles=legend, loc="lower left", ncol=5, fontsize=6.6, frameon=False, bbox_to_anchor=(0.0, -0.32))

    for ext in ("pdf", "png"):
        out = HERE / f"f1_scrubber.{ext}"
        fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.12)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()

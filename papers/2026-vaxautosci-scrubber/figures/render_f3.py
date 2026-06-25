#!/usr/bin/env python3
"""Render Figure 3, interruption recovery, from data/lights_out_run.json.

The same recorded run folded to two cursor positions. At the beam-loss instant
the first projection is an open interval (in-flight marker, no outcome) and the
run is Held; folded to the end it is closed (outcome recorded) and the run is
Completed. The open interval is a function of where the cursor is, not a
permanent dangling record: that is the replay-native answer to "what was in
flight when the beam dropped" (T1).

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

HERE = Path(__file__).parent
DATA = json.loads((HERE.parent / "data" / "lights_out_run.json").read_text())

C_OPEN = "#C0392B"
C_OK = "#2E7D32"
C_MARK = "#3B6EA5"


def _parse(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    acts = DATA["activities"]
    prov = DATA["provenance"]
    t0 = _parse(DATA["run"]["events"][0]["at"])

    def secs(s: str) -> float:
        return (_parse(s) - t0).total_seconds()

    proj = {a["result"]: secs(a["sampled_at"]) for a in acts
            if a["payload"].get("action_name") == "acquire_first_projection"}
    begin, end = proj["in_flight"], proj["ok"]
    beam_loss = secs(prov["beam_loss_at"])
    beam_back = secs(prov["beam_back_at"])
    xlo, xhi = begin - 8, end + 12

    fig, axes = plt.subplots(2, 1, figsize=(5.3, 3.0), sharex=True)

    def lane(ax, *, cursor, closed, run_status, title):
        ax.axvspan(beam_loss, min(cursor, beam_back) if not closed else beam_back,
                   color="#F0F0F0", zorder=0)
        ax.scatter([begin], [0], marker="D", s=46, color=C_MARK, edgecolors="white",
                   linewidths=0.5, zorder=3)
        if closed:
            ax.plot([begin, end], [0, 0], color=C_OK, lw=6, solid_capstyle="butt", alpha=0.5, zorder=1)
            ax.scatter([end], [0], marker="^", s=58, color=C_OK, edgecolors="white", linewidths=0.5, zorder=3)
            ax.annotate("outcome recorded", (end, 0), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=6.4, color=C_OK)
        else:
            ax.plot([begin, cursor], [0, 0], color=C_OPEN, lw=5, ls=(0, (4, 3)), alpha=0.85, zorder=1)
            ax.annotate("", xy=(cursor + 0.4, 0), xytext=(cursor - 1.6, 0),
                        arrowprops={"arrowstyle": "-|>", "color": C_OPEN, "lw": 1.3})
            ax.annotate("in flight: no outcome", (begin, 0), textcoords="offset points", xytext=(2, 9),
                        ha="left", fontsize=6.4, color=C_OPEN, fontweight="bold")
        ax.axvline(cursor, color=C_OPEN if not closed else C_OK, ls="--", lw=1.2, zorder=4)
        ax.text(cursor, 0.62, title, color=(C_OPEN if not closed else C_OK), fontsize=6.8,
                ha="center", va="bottom", fontweight="bold")
        ax.text(xlo + 1, -0.66, f"run: {run_status}", fontsize=6.6, ha="left", va="center",
                color="#444444")
        ax.set_yticks([0])
        ax.set_yticklabels(["First\nprojection"], fontsize=7)
        ax.set_ylim(-0.95, 1.0)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)

    lane(axes[0], cursor=beam_loss, closed=False, run_status="HELD (RunSupervisor)",
         title="cursor at beam loss")
    lane(axes[1], cursor=end + 4, closed=True, run_status="COMPLETED",
         title="cursor after resume")

    axes[0].set_title("Interruption recovery: one run, two cursor positions", fontsize=9, loc="left")
    axes[1].set_xlim(xlo, xhi)
    axes[1].set_xlabel("time (s; synthetic spacing)", fontsize=8)
    axes[1].tick_params(axis="x", labelsize=7)

    fig.tight_layout()
    for ext in ("pdf", "png"):
        out = HERE / f"f3_crash.{ext}"
        fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0.1)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render Figure 3, interruption recovery, from data/lights_out_run.json.

The same recorded run folded to two cursor positions. At the beam-loss instant
the interrupted projection is an open interval (in-flight marker, no outcome) and the
run is Held; folded to the end it is closed (outcome recorded) and the run is
Completed. The open interval is a function of where the cursor is, not a
permanent dangling record: that is the replay-native answer to "what was in
flight when the beam dropped" (T1).

Single-column figure: rendered at one column width.
Run: uv run --no-project --with matplotlib python figures/render_f3.py
"""

from __future__ import annotations

import datetime as dt
import json

import _style as s

DATA = json.loads((s.HERE.parent / "data" / "lights_out_run.json").read_text())


def _parse(x: str) -> dt.datetime:
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def main() -> None:
    acts = DATA["activities"]
    prov = DATA["provenance"]
    t0 = _parse(DATA["run"]["events"][0]["at"])

    def secs(x: str) -> float:
        return (_parse(x) - t0).total_seconds()

    # The interrupted projection carries an in-flight marker (begin) and, after
    # recovery, its outcome (end); find it by its in-flight result.
    projs = [a for a in acts if a["payload"].get("action_name") == "acquire_projection"]
    idx = next(a["payload"]["params"]["index"] for a in projs if a["result"] == "in_flight")
    times = {a["result"]: secs(a["sampled_at"]) for a in projs
             if a["payload"]["params"]["index"] == idx}
    begin, end = times["in_flight"], times["ok"]
    beam_loss = secs(prov["beam_loss_at"])
    beam_back = secs(prov["beam_back_at"])
    xlo, xhi = begin - 8, end + 14

    import matplotlib.pyplot as plt
    s.install()
    fig, axes = plt.subplots(2, 1, figsize=(s.COL_WIDTH, 2.75), sharex=True,
                             layout="constrained")

    def lane(ax, *, cursor, closed, run_status, tag):
        ax.axvspan(beam_loss, beam_back if closed else min(cursor, beam_back),
                   color=s.HELD, zorder=0)
        accent = s.GOOD if closed else s.ALARM
        ax.scatter([begin], [0], marker="^", s=52, color=accent,
                   edgecolors="white", linewidths=0.6, zorder=3)
        if closed:
            ax.plot([begin, end], [0, 0], color=s.GOOD, lw=5,
                    solid_capstyle="round", alpha=0.45, zorder=1)
            ax.scatter([end], [0], marker="^", s=52, color=s.GOOD,
                       edgecolors="white", linewidths=0.6, zorder=3)
            ax.annotate("outcome recorded", (end, 0), textcoords="offset points",
                        xytext=(0, 9), ha="center", fontsize=s.SIZE["small"],
                        color=s.GOOD)
        else:
            ax.plot([begin, cursor], [0, 0], color=s.ALARM, lw=4.5,
                    ls=(0, (0.9, 0.8)), dash_capstyle="butt", alpha=0.9, zorder=1)
            ax.annotate("", xy=(cursor + 0.4, 0), xytext=(cursor - 1.6, 0),
                        arrowprops={"arrowstyle": "-|>", "color": s.ALARM, "lw": 1.2})
            ax.annotate("in flight: no outcome", (begin, 0),
                        textcoords="offset points", xytext=(2, 9), ha="left",
                        fontsize=s.SIZE["small"], color=s.ALARM, fontweight="bold")
        ax.axvline(cursor, color=accent, ls="--", lw=1.1, zorder=4)
        ax.text(cursor, 0.66, tag, color=accent, fontsize=s.SIZE["small"],
                ha="center", va="bottom", fontweight="bold")
        ax.text(xlo + 1, -0.7, f"run: {run_status}", fontsize=s.SIZE["small"],
                ha="left", va="center", color=s.SUBINK)
        ax.set_yticks([0])
        ax.set_yticklabels(["Projection 3"], fontsize=s.SIZE["tick"])
        ax.set_ylim(-1.0, 1.05)
        s.despine(ax, keep=("bottom",))

    lane(axes[0], cursor=beam_loss, closed=False, run_status="HELD (supervisor)",
         tag="cursor at beam loss")
    lane(axes[1], cursor=end + 5, closed=True, run_status="COMPLETED",
         tag="cursor after resume")

    s.title(axes[0], "Interruption recovery: one run, two cursors")
    axes[1].set_xlim(xlo, xhi)
    axes[1].set_xlabel("time (s; synthetic spacing)", fontsize=s.SIZE["label"])
    axes[1].tick_params(axis="x", labelsize=s.SIZE["tick"])

    s.save(fig, "f3_crash")


if __name__ == "__main__":
    main()

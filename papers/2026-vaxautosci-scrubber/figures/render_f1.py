#!/usr/bin/env python3
"""Render Figure 1, the replay scrubber, from data/lights_out_run.json.

Static rendering of the interactive scrubber over one agent-supervised
run: a run-lifecycle / who-drove-it lane (operator vs supervisor),
per-iteration convergence brackets colored by verdict (the rotation-axis
centering search), activity swim-lanes, a shaded held band, and a fold-to-
version cursor parked at the beam-loss instant, where the first projection is an
open interval (in flight, no outcome yet).

Full-width figure: rendered at the full text width.
Run: uv run --no-project --with matplotlib python figures/render_f1.py
"""

from __future__ import annotations

import datetime as dt
import json

import _style as s
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnchoredOffsetbox, TextArea, VPacker

DATA = json.loads((s.HERE.parent / "data" / "lights_out_run.json").read_text())

LANE_Y = {"setpoint": 2, "action": 1, "check": 0}
LANE_LABEL = {2: "Setpoint", 1: "Acquire", 0: "Check"}
LANE_COLOR = {"setpoint": s.OPERATOR, "action": s.SUBINK, "check": s.STATE}
LANE_MARKER = {"setpoint": "s", "action": "^", "check": "o"}
Y_BRACKET = 3.0
Y_RUN = 3.9


def _parse(x: str) -> dt.datetime:
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def main() -> None:
    acts = DATA["activities"]
    iters = DATA["iterations"]
    run_events = DATA["run"]["events"]
    prov = DATA["provenance"]
    t0 = _parse(run_events[0]["at"])

    def secs(x: str) -> float:
        return (_parse(x) - t0).total_seconds()

    cursor = secs(prov["cursor_at"])
    beam_loss = secs(prov["beam_loss_at"])
    beam_back = secs(prov["beam_back_at"])
    xmax = max(secs(e["at"]) for e in run_events)

    fig, ax = s.figure(s.FULL_WIDTH, 3.5)

    # Faint lane baselines anchor the swim-lanes.
    for y in LANE_Y.values():
        ax.axhline(y, color=s.RULE, lw=0.6, zorder=0)

    # Held band: the whole run is held between beam loss and beam back.
    ax.axvspan(beam_loss, beam_back, color=s.HELD, zorder=0)
    ax.text((beam_loss + beam_back) / 2, Y_RUN + 0.30, "held", ha="center",
            va="bottom", fontsize=s.SIZE["small"], color=s.MUTE, style="italic")

    # Run lifecycle / who-drove-it lane.
    label_pos = {"RunStarted": (0, 9, "center"), "RunHeld": (7, 2, "left"),
                 "RunResumed": (0, 9, "center"), "RunCompleted": (0, 9, "center")}
    for ev in run_events:
        x = secs(ev["at"])
        agent = ev["role"] == "agent"
        col = s.AGENT if agent else s.OPERATOR
        ax.scatter([x], [Y_RUN], marker=("D" if agent else "s"), s=52, color=col,
                   edgecolors="white", linewidths=0.7, zorder=4)
        label = {"RunStarted": "started", "RunHeld": "held", "RunResumed": "resumed",
                 "RunCompleted": "completed"}[ev["type"]]
        who = "supervisor" if agent else "operator"
        dx, dy, ha = label_pos[ev["type"]]
        ax.annotate(f"{label}\n({who})", (x, Y_RUN), textcoords="offset points",
                    xytext=(dx, dy), ha=ha, fontsize=s.SIZE["small"], color=col,
                    linespacing=1.0)

    # Convergence brackets, colored by verdict.
    for it in iters:
        a, b = secs(it["started_at"]), secs(it["ended_at"])
        col = s.GOOD if it["converged"] else s.WARN
        ax.plot([a, b], [Y_BRACKET, Y_BRACKET], color=col, lw=4.5,
                solid_capstyle="butt", alpha=0.9)
        for x in (a, b):
            ax.plot([x, x], [Y_BRACKET - 0.1, Y_BRACKET + 0.1], color=col, lw=1.5)
        ax.text((a + b) / 2, Y_BRACKET + 0.17, f"i{it['iteration_index']}",
                ha="center", va="bottom", fontsize=s.SIZE["small"], color=col)
    ax.text(secs(iters[-1]["ended_at"]) + 2.5, Y_BRACKET, "centering converged",
            fontsize=s.SIZE["small"], va="center", ha="left", color=s.GOOD)

    # Activity swim-lanes (alignment), plus the first science projection.
    for a in acts:
        if a["payload"].get("action_name") == "acquire_first_projection":
            continue
        x, y = secs(a["sampled_at"]), LANE_Y[a["step_kind"]]
        ax.scatter([x], [y], marker=LANE_MARKER[a["step_kind"]], s=46,
                   color=LANE_COLOR[a["step_kind"]], zorder=3, edgecolors="white",
                   linewidths=0.6)
        if a["step_kind"] == "check":
            ax.annotate(f"{a['payload']['actual']:.2f}", (x, y),
                        textcoords="offset points", xytext=(0, -11), ha="center",
                        fontsize=s.SIZE["small"], color=s.STATE)

    # First projection: in-flight from begin to the cursor (open), faint after resume.
    proj = {a["result"]: secs(a["sampled_at"]) for a in acts
            if a["payload"].get("action_name") == "acquire_first_projection"}
    y = LANE_Y["action"]
    begin = proj["in_flight"]
    ax.plot([begin, cursor], [y, y], color=s.ALARM, lw=4.5, ls=(0, (4, 2.6)),
            alpha=0.9, zorder=2)
    ax.scatter([begin], [y], marker="D", s=42, color=s.ALARM, edgecolors="white",
               linewidths=0.6, zorder=3)
    ax.annotate("first projection:\nin flight", ((begin + cursor) / 2, y),
                textcoords="offset points", xytext=(0, 8), ha="center",
                fontsize=s.SIZE["small"], color=s.ALARM, fontweight="bold",
                linespacing=1.0)
    ax.scatter([proj["ok"]], [y], marker="^", s=42, color=s.SUBINK, alpha=0.35,
               edgecolors="white", linewidths=0.5, zorder=3)
    ax.annotate("completes\nafter resume", (proj["ok"], y),
                textcoords="offset points", xytext=(0, -17), ha="center",
                fontsize=s.SIZE["small"], color=s.MUTE, linespacing=1.0)

    # Fold-to-version cursor at the beam-loss instant.
    ax.axvline(cursor, color=s.ALARM, ls="--", lw=1.3, zorder=5)
    ax.text(cursor, Y_RUN + 0.7, "cursor: beam loss", color=s.ALARM,
            fontsize=s.SIZE["anno"], ha="center", va="bottom", fontweight="bold")

    # Folded-state readout: an evenly padded info card parked in the held band.
    def _row(text, color, weight="normal", size=s.SIZE["small"]):
        return TextArea(text, textprops={"color": color, "fontweight": weight,
                                         "fontsize": size})

    readout = VPacker(pad=0, sep=4.5, align="left", children=[
        _row("Folded state at cursor", s.ALARM, "bold", s.SIZE["anno"]),
        _row("alignment: converged (0.30 px)", s.INK),
        _row("first projection: in flight", s.INK),
        _row("run: held by supervisor", s.INK),
        _row("fidelity: verified", s.INK),
    ])
    card = AnchoredOffsetbox(loc="center", child=readout, pad=0.6, borderpad=0,
                             frameon=True, bbox_to_anchor=(0.57, 0.46),
                             bbox_transform=ax.transAxes)
    card.patch.set(boxstyle="round,pad=0,rounding_size=0.5", facecolor="white",
                   edgecolor=s.RULE, linewidth=1.0)
    card.set_zorder(6)
    ax.add_artist(card)

    ax.set_yticks(list(LANE_LABEL))
    ax.set_yticklabels([LANE_LABEL[k] for k in LANE_LABEL], fontsize=s.SIZE["label"])
    ax.set_ylim(-1.0, Y_RUN + 1.15)
    ax.set_xlim(-4, xmax + 6)
    ax.set_xlabel("time (s; synthetic spacing, see data/README.md)",
                  fontsize=s.SIZE["label"])
    ax.tick_params(axis="x", labelsize=s.SIZE["tick"])
    s.despine(ax, keep=("bottom",))
    s.title(ax, "Replay scrubber: an agent-supervised run at APS 2-BM")

    legend = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor=s.OPERATOR,
               markersize=6.5, label="operator"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=s.AGENT,
               markersize=6.5, label="supervisor"),
        Line2D([0], [0], color=s.WARN, lw=4, label="bracket: open"),
        Line2D([0], [0], color=s.GOOD, lw=4, label="bracket: converged"),
        Line2D([0], [0], color=s.ALARM, lw=3, ls=(0, (4, 2.6)), label="in-flight (open)"),
    ]
    ax.legend(handles=legend, loc="lower left", ncol=5, fontsize=s.SIZE["legend"],
              frameon=False, bbox_to_anchor=(0.0, -0.235), handletextpad=0.5,
              columnspacing=1.3)

    s.save(fig, "f1_scrubber")


if __name__ == "__main__":
    main()

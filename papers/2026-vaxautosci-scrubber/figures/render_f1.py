#!/usr/bin/env python3
"""Render Figure 1, the replay scrubber, from data/lights_out_run.json.

Static rendering of the interactive scrubber over one agent-supervised
run: a run-lifecycle / who-drove-it lane (operator vs supervisor),
per-iteration convergence bands colored by verdict (the rotation-axis
centering search), activity swim-lanes, a shaded held band, and a fold-to-
version cursor parked at the beam-loss instant, where the third projection is an
open interval (in flight, no outcome yet); the science scan continues after
resume.

Full-width figure: rendered at the full text width.
Run: uv run --no-project --with matplotlib python figures/render_f1.py
"""

from __future__ import annotations

import datetime as dt
import json

import _style as s
from matplotlib.lines import Line2D
from matplotlib.offsetbox import AnchoredOffsetbox, TextArea, VPacker
from matplotlib.patches import Patch, Rectangle

DATA = json.loads((s.HERE.parent / "data" / "lights_out_run.json").read_text())

LANE_Y = {"setpoint": 2, "action": 1, "check": 0}
LANE_LABEL = {2: "Setpoint", 1: "Acquire", 0: "Check"}
LANE_COLOR = {"setpoint": s.INK, "action": s.SUBINK, "check": s.STATE}
LANE_MARKER = {"setpoint": "s", "action": "^", "check": "o"}
Y_OUTPUT = -1.4        # output lane (dataset written to disk), below the swim-lanes
Y_BAND = (-0.6, 2.55)  # iteration band spans the three acquisition swim-lanes
Y_PERMIT = 3.2         # beam-permit lane (safety envelope the supervisor gates on)
Y_RUN = 4.0            # run-lifecycle / who-drove-it lane
Y_PHASE = (4.95, 5.30)  # top strip of color-coded phase bars

# The run's three phases, color-coded (light tint + dark label).
PHASE_STYLE = {
    "Alignment (converged)": ("#DCE6F2", "#2C5282"),
    "Scan": ("#D7ECE9", "#1D6F66"),
    "Save": ("#E7E1F2", "#5B4A8A"),
}


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

    fig, ax = s.figure(s.FULL_WIDTH, 4.4)

    # Faint lane baselines anchor the swim-lanes.
    for y in LANE_Y.values():
        ax.axhline(y, color=s.RULE, lw=0.6, zorder=0)

    # Held band: the whole run is held between beam loss and beam back.
    ax.axvspan(beam_loss, beam_back, color=s.HELD, zorder=0)
    ax.text((beam_loss + beam_back) / 2, Y_RUN + 0.28, "held", ha="center",
            va="bottom", fontsize=s.SIZE["small"], color=s.MUTE, style="italic")

    # Phase anchors from recorded activity times.
    proj_times = sorted(secs(a["sampled_at"]) for a in acts
                        if a["payload"].get("action_name") == "acquire_projection")
    save_time = next((secs(a["sampled_at"]) for a in acts
                      if a["payload"].get("action_name") == "write_dataset"), None)
    align_end = secs(iters[-1]["ended_at"]) + 1.5
    scan_start = align_end  # the fly-scan setup is the head of the scan; no gap
    scan_end = (save_time - 6) if save_time is not None else proj_times[-1] + 6
    run_done = max(secs(e["at"]) for e in run_events)

    # Color-coded phase bars across the top: Alignment, Scan, Save.
    plo, phi = Y_PHASE
    phases = [("Alignment (converged)", -3, align_end), ("Scan", scan_start, scan_end)]
    if save_time is not None:
        phases.append(("Save", scan_end, save_time + 6))
    for name, x0, x1 in phases:
        face, ink = PHASE_STYLE[name]
        ax.add_patch(Rectangle((x0, plo), x1 - x0, phi - plo, facecolor=face,
                               edgecolor="none", zorder=0))
        ax.text((x0 + x1) / 2, (plo + phi) / 2, name, ha="center", va="center",
                fontsize=s.SIZE["small"], color=ink, fontweight="bold")

    # Beam-permit lane: the safety envelope the supervisor gates hold/resume on.
    # Permit is satisfied except across the hold (beam loss to beam back).
    ax.axhline(Y_PERMIT, color=s.RULE, lw=0.6, zorder=0)
    for x0, x1 in ((-3, beam_loss), (beam_back, run_done)):
        ax.plot([x0, x1], [Y_PERMIT, Y_PERMIT], color=s.GOOD, lw=3.0,
                solid_capstyle="butt", alpha=0.85, zorder=2)
    ax.plot([beam_loss, beam_back], [Y_PERMIT, Y_PERMIT], color=s.ALARM, lw=3.0,
            ls=(0, (1.2, 1.2)), dash_capstyle="butt", alpha=0.9, zorder=2)
    ax.annotate("lost", ((beam_loss + beam_back) / 2, Y_PERMIT),
                textcoords="offset points", xytext=(0, 4), ha="center",
                fontsize=s.SIZE["small"], color=s.ALARM)

    # Run lifecycle / who-drove-it lane.
    label_pos = {"RunStarted": (0, 9, "center"), "RunHeld": (0, 9, "center"),
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

    # Each iteration is one setpoint-acquire-check cycle: shade its span across
    # the lanes, tinted by verdict, capped with a thin verdict-colored rule.
    band_lo, band_hi = Y_BAND
    for it in iters:
        a, b = secs(it["started_at"]), secs(it["ended_at"])
        converged = it["converged"]
        col = s.GOOD if converged else s.WARN
        ax.add_patch(Rectangle((a, band_lo), b - a, band_hi - band_lo,
                               facecolor=s.GOOD_BG if converged else s.WARN_BG,
                               edgecolor="none", zorder=-1))
        ax.plot([a, b], [band_hi, band_hi], color=col, lw=2.0,
                solid_capstyle="butt", zorder=1)
        ax.text((a + b) / 2, band_hi + 0.12, f"i{it['iteration_index']}",
                ha="center", va="bottom", fontsize=s.SIZE["small"], color=col)
    ax.text((secs(iters[0]["started_at"]) + secs(iters[-1]["ended_at"])) / 2,
            band_lo - 0.18, "centering converged", fontsize=s.SIZE["small"],
            va="top", ha="center", color=s.GOOD)

    # Activity swim-lanes (alignment). Science projections are drawn separately.
    for a in acts:
        if (a["payload"].get("role") == "taxi"
                or a["payload"].get("action_name") in ("acquire_projection",
                                                       "fly_scan_prep", "write_dataset")):
            continue
        x, y = secs(a["sampled_at"]), LANE_Y[a["step_kind"]]
        ax.scatter([x], [y], marker=LANE_MARKER[a["step_kind"]], s=46,
                   color=LANE_COLOR[a["step_kind"]], zorder=3, edgecolors="white",
                   linewidths=0.6)
        if a["step_kind"] == "check":
            ax.annotate(f"{a['payload']['actual']:.2f}", (x, y),
                        textcoords="offset points", xytext=(0, -11), ha="center",
                        fontsize=s.SIZE["small"], color=s.STATE)

    # Science projections (acquire_projection). The interrupted projection has an
    # in-flight marker (before the beam loss) and an ok marker (after recovery);
    # identify it by its in-flight result.
    projs = [a for a in acts if a["payload"].get("action_name") == "acquire_projection"]
    y = LANE_Y["action"]
    inflight = next(secs(a["sampled_at"]) for a in projs if a["result"] == "in_flight")
    ok_times = sorted(secs(a["sampled_at"]) for a in projs if a["result"] == "ok")
    pre_ok = [t for t in ok_times if t < cursor]
    post_ok = [t for t in ok_times if t > cursor]
    reacq = post_ok[0]

    # Before the cursor the scan was acquiring: completed projections are solid
    # (closed); the interrupted one is an open (dashed) interval to the cursor.
    if pre_ok:
        ax.plot([pre_ok[0], inflight], [y, y], color=s.SUBINK, lw=4.5, alpha=0.5,
                solid_capstyle="butt", zorder=1)
        ax.scatter(pre_ok, [y] * len(pre_ok), marker="^", s=40, color=s.SUBINK,
                   edgecolors="white", linewidths=0.6, zorder=3)
    ax.plot([inflight, cursor], [y, y], color=s.ALARM, lw=4.5, ls=(0, (0.9, 0.8)),
            dash_capstyle="butt", alpha=0.9, zorder=2)
    ax.scatter([inflight], [y], marker="^", s=52, color=s.ALARM, edgecolors="white",
               linewidths=0.6, zorder=3)
    ax.annotate("projection 3:\nin flight", ((inflight + cursor) / 2, y),
                textcoords="offset points", xytext=(0, 8), ha="center",
                fontsize=s.SIZE["small"], color=s.ALARM, fontweight="bold",
                linespacing=1.0)

    # A fly-scan restart (taxi the rotary stage to constant velocity, re-arm the
    # PSO) is needed both before the first frame and again after the hold; show
    # each as a hatched band.
    taxi_times = sorted(secs(a["sampled_at"]) for a in acts if a["payload"].get("role") == "taxi")
    first_proj = min(pre_ok + [inflight])
    for x0, x1 in ((taxi_times[0] - 2, first_proj), (beam_back, reacq)):
        ax.axvspan(x0, x1, facecolor="none", hatch="////", edgecolor=s.MUTE,
                   linewidth=0.0, alpha=0.6, zorder=0)
        ax.annotate("fly-scan\nsetup", ((x0 + x1) / 2, LANE_Y["action"]),
                    textcoords="offset points", xytext=(0, 20), ha="center",
                    va="center", fontsize=s.SIZE["small"], color=s.SUBINK,
                    linespacing=0.9)

    # After recovery: the re-acquired projection and the rest of the scan,
    # ghosted since they are past the parked cursor.
    ax.plot([post_ok[0], post_ok[-1]], [y, y], color=s.MUTE, lw=4.5, alpha=0.4,
            solid_capstyle="butt", zorder=1)
    ax.scatter(post_ok, [y] * len(post_ok), marker="^", s=34, color=s.MUTE,
               alpha=0.55, edgecolors="white", linewidths=0.5, zorder=3)
    ax.annotate("scan resumes,\nruns to completion", (post_ok[len(post_ok) // 2], y),
                textcoords="offset points", xytext=(0, -17), ha="center",
                fontsize=s.SIZE["small"], color=s.MUTE, linespacing=1.0)

    # Data save: the collected dataset is written to disk at the end, on its own
    # output lane (an action, not an acquisition). Past the cursor, so ghosted.
    if save_time is not None:
        ax.axhline(Y_OUTPUT, color=s.RULE, lw=0.6, zorder=0)
        ax.plot([post_ok[-1], save_time], [y, Y_OUTPUT], color=s.MUTE, lw=1.0,
                ls=(0, (2, 2)), alpha=0.4, zorder=1)
        ax.scatter([save_time], [Y_OUTPUT], marker="p", s=52, color=s.MUTE,
                   alpha=0.6, edgecolors="white", linewidths=0.5, zorder=3)
        ax.annotate("dataset written\n(HDF5)", (save_time, Y_OUTPUT),
                    textcoords="offset points", xytext=(0, 9), ha="center",
                    fontsize=s.SIZE["small"], color=s.MUTE, linespacing=0.9)

    # The rotary stage rotates continuously (fly-scan), paused during the hold and
    # the restart: a faint span on the setpoint lane shows the motor moving.
    rot = [secs(a["sampled_at"]) for a in acts if a["payload"].get("role") == "fly_scan"]
    if rot:
        ysp = LANE_Y["setpoint"]
        for x0, x1 in ((first_proj, beam_loss), (reacq, post_ok[-1])):
            ax.plot([x0, x1], [ysp, ysp], color=s.MUTE, lw=2.2, alpha=0.5,
                    solid_capstyle="round", zorder=1)
        ax.annotate("fly-scan rotation, 0-180 deg", ((reacq + post_ok[-1]) / 2, ysp),
                    textcoords="offset points", xytext=(0, 8), ha="center",
                    fontsize=s.SIZE["small"], color=s.MUTE)

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
        _row("projections: 2 done, #3 in flight", s.INK),
        _row("run: held by supervisor", s.INK),
        _row("fidelity: verified", s.INK),
    ])
    card = AnchoredOffsetbox(loc="center", child=readout, pad=0.6, borderpad=0,
                             frameon=True, bbox_to_anchor=((beam_loss + beam_back) / 2, 0.46),
                             bbox_transform=ax.get_xaxis_transform())
    card.patch.set(boxstyle="round,pad=0,rounding_size=0.5", facecolor="white",
                   edgecolor=s.RULE, linewidth=1.0)
    card.set_zorder(6)
    ax.add_artist(card)

    yticks = [Y_OUTPUT] + list(LANE_LABEL) + [Y_PERMIT, Y_RUN]
    ylabels = ["Output"] + [LANE_LABEL[k] for k in LANE_LABEL] + ["Beam permit", "Run"]
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=s.SIZE["label"])
    ax.set_ylim(Y_OUTPUT - 0.7, Y_PHASE[1] + 0.35)
    ax.set_xlim(-6, xmax + 6)
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
        Patch(facecolor=s.WARN_BG, edgecolor=s.WARN, label="iteration: open"),
        Patch(facecolor=s.GOOD_BG, edgecolor=s.GOOD, label="iteration: converged"),
        Line2D([0], [0], color=s.ALARM, lw=4.5, ls=(0, (0.9, 0.8)),
               dash_capstyle="butt", label="in-flight (open)"),
        Line2D([0], [0], color=s.GOOD, lw=3, label="beam permit OK"),
    ]
    ax.legend(handles=legend, loc="lower left", ncol=6, fontsize=s.SIZE["legend"],
              frameon=False, bbox_to_anchor=(0.0, -0.235), handletextpad=0.5,
              columnspacing=1.3)

    s.save(fig, "f1_scrubber")


if __name__ == "__main__":
    main()

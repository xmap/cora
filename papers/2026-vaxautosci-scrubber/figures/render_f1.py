#!/usr/bin/env python3
"""Render Figure 1, the replay scrubber, from data/lights_out_run.json.

Static rendering of the interactive scrubber over one robot-loaded, lights-out
session: a sample-changing robot loads two samples in turn (a sample-custody
lane and a robot mount/dismount lane), each sample is recentered (per-sample
convergence bands colored by verdict) and scanned, and on the second sample the
beam drops mid-scan (the third projection is an open interval), the supervisor
holds and resumes, and the fly-scan restarts. The fold-to-version cursor is
parked at the beam-loss instant.

Lanes are grouped by subsystem, top to bottom: sample handling (custody, robot),
run and safety (run lifecycle, beam permit), then the science swim-lanes.

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

# Lane y-coordinates, grouped by subsystem (top to bottom). The run/safety and
# sample-handling lanes are spaced a little wider than the science swim-lanes
# because each carries compact two-line marker labels above and below its
# baseline; gaps are kept as tight as those labels allow.
Y_OUTPUT = -1.15       # dataset written to disk, below the science swim-lanes
Y_BAND = (-0.5, 2.35)  # iteration band spans the three science swim-lanes
Y_PERMIT = 2.9         # run + safety group
Y_RUN = 3.75
Y_ROBOT = 4.85         # sample-handling group
Y_CUSTODY = 5.75
Y_PHASE = (6.35, 6.65)  # top strip: per-sample phase bars

PHASE_STYLE = {
    "Sample A": ("#DCE6F2", "#2C5282"),
    "Sample B": ("#D7ECE9", "#1D6F66"),
}


def _parse(x: str) -> dt.datetime:
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def main() -> None:
    acts = DATA["activities"]
    iters = DATA["iterations"]
    runs = DATA["runs"]
    samples = DATA["samples"]
    robot = DATA["robot"]
    prov = DATA["provenance"]

    all_run_events = [e for r in runs for e in r["events"]]
    t0 = min(_parse(e["at"]) for e in all_run_events)

    def secs(x: str) -> float:
        return (_parse(x) - t0).total_seconds()

    cursor = secs(prov["cursor_at"])
    beam_loss = secs(prov["beam_loss_at"])
    beam_back = secs(prov["beam_back_at"])
    xmax = max(secs(a["sampled_at"]) for a in acts)

    fig, ax = s.figure(s.FULL_WIDTH, 4.6)

    for y in LANE_Y.values():
        ax.axhline(y, color=s.RULE, lw=0.6, zorder=0)

    # Held band across the hold (beam loss to beam back), spanning the figure.
    # No standalone label: the band is read together with the dotted run-state
    # line, the beam-permit "lost" segment, and the "held (supervisor)" marker.
    ax.axvspan(beam_loss, beam_back, color=s.HELD, zorder=0)

    # ----- Per-sample phase bars across the top -----
    plo, phi = Y_PHASE
    for sm in samples:
        c0, c1 = secs(sm["mount_at"]) - 3.0, secs(sm["dismount_at"]) + 1.5
        name = f"Sample {'A' if sm['index'] == 1 else 'B'}"
        face, ink = PHASE_STYLE[name]
        ax.add_patch(Rectangle((c0, plo), c1 - c0, phi - plo, facecolor=face,
                               edgecolor="none", zorder=0))
        ax.text((c0 + c1) / 2, (plo + phi) / 2, name, ha="center", va="center",
                fontsize=s.SIZE["small"], color=ink, fontweight="bold")

    # ===== SAMPLE HANDLING group =====
    # Sample-custody lane: a band while a Subject is mounted, a gap during the
    # robot swap. The state answer "which sample is on the stage?" at any cursor.
    ax.axhline(Y_CUSTODY, color=s.RULE, lw=0.6, zorder=0)
    for sm in samples:
        a0, a1 = secs(sm["mount_at"]), secs(sm["dismount_at"])
        label = "A" if sm["index"] == 1 else "B"
        ax.add_patch(Rectangle((a0, Y_CUSTODY - 0.12), a1 - a0, 0.24,
                               facecolor=s.SUBINK, edgecolor="none", alpha=0.32, zorder=1))
        ax.plot([a0, a1], [Y_CUSTODY, Y_CUSTODY], color=s.SUBINK, lw=1.4,
                solid_capstyle="butt", zorder=2)
        ax.text((a0 + a1) / 2, Y_CUSTODY + 0.14, f"sample {label} mounted",
                ha="center", va="bottom", fontsize=s.SIZE["small"], color=s.SUBINK)

    # Robot lane: Manipulator mount/dismount markers (the custody-band edges).
    # mount labels above, dismount below, so the adjacent A-dismount / B-mount
    # pair at the sample swap does not collide.
    ax.axhline(Y_ROBOT, color=s.RULE, lw=0.6, zorder=0)
    for ev in robot["events"]:
        x = secs(ev["at"])
        ax.scatter([x], [Y_ROBOT], marker="D", s=44, color=s.STATE,
                   edgecolors="white", linewidths=0.7, zorder=4)
        dy = 7 if ev["action"] == "mount" else -14
        ax.annotate(ev["action"], (x, Y_ROBOT), textcoords="offset points",
                    xytext=(0, dy), ha="center", fontsize=s.SIZE["small"], color=s.STATE)

    # ===== RUN & SAFETY group =====
    # Run-lifecycle: one state line per run (started..completed), dotted while
    # held. Markers overlay the line: operator square, supervisor diamond.
    ax.axhline(Y_RUN, color=s.RULE, lw=0.6, zorder=0)
    label_word = {"RunStarted": "started", "RunHeld": "held",
                  "RunResumed": "resumed", "RunCompleted": "completed"}
    for r in runs:
        evs = {e["type"]: secs(e["at"]) for e in r["events"]}
        if "RunHeld" in evs and "RunResumed" in evs:
            segs = [(evs["RunStarted"], evs["RunHeld"], False),
                    (evs["RunHeld"], evs["RunResumed"], True),
                    (evs["RunResumed"], evs["RunCompleted"], False)]
        else:
            segs = [(evs["RunStarted"], evs["RunCompleted"], False)]
        for x0, x1, held in segs:
            ax.plot([x0, x1], [Y_RUN, Y_RUN], color=s.INK, lw=1.6,
                    ls=((0, (1.2, 1.2)) if held else "solid"),
                    dash_capstyle="butt", solid_capstyle="butt", zorder=2)
        # started/held label above the lane, completed/resumed below, so the
        # A-completed / B-started pair at the swap and the held/resumed pair do
        # not overlap.
        below = {"RunCompleted", "RunResumed"}
        for e in r["events"]:
            x = secs(e["at"])
            agent = e["role"] == "agent"
            col = s.AGENT if agent else s.OPERATOR
            ax.scatter([x], [Y_RUN], marker=("D" if agent else "s"), s=48, color=col,
                       edgecolors="white", linewidths=0.7, zorder=4)
            who = "supervisor" if agent else "operator"
            dy, va = (-22, "top") if e["type"] in below else (9, "bottom")
            ax.annotate(f"{label_word[e['type']]}\n({who})", (x, Y_RUN),
                        textcoords="offset points", xytext=(0, dy), ha="center",
                        va=va, fontsize=s.SIZE["small"], color=col, linespacing=1.0)

    # Beam-permit lane: satisfied except across the hold.
    ax.axhline(Y_PERMIT, color=s.RULE, lw=0.6, zorder=0)
    run_done = max(secs(e["at"]) for e in all_run_events)
    for x0, x1 in ((-3, beam_loss), (beam_back, run_done)):
        ax.plot([x0, x1], [Y_PERMIT, Y_PERMIT], color=s.GOOD, lw=3.0,
                solid_capstyle="butt", alpha=0.85, zorder=2)
    ax.plot([beam_loss, beam_back], [Y_PERMIT, Y_PERMIT], color=s.ALARM, lw=3.0,
            ls=(0, (1.2, 1.2)), dash_capstyle="butt", alpha=0.9, zorder=2)
    ax.annotate("lost", ((beam_loss + beam_back) / 2, Y_PERMIT),
                textcoords="offset points", xytext=(0, 4), ha="center",
                fontsize=s.SIZE["small"], color=s.ALARM)

    # ===== SCIENCE group =====
    # Per-sample iteration bands (setpoint-acquire-check cycles), tinted by verdict.
    band_lo, band_hi = Y_BAND
    for it in iters:
        a, b = secs(it["started_at"]), secs(it["ended_at"])
        converged = it["converged"]
        col = s.GOOD if converged else s.WARN
        ax.add_patch(Rectangle((a, band_lo), b - a, band_hi - band_lo,
                               facecolor=s.GOOD_BG if converged else s.WARN_BG,
                               edgecolor="none", zorder=-1))
        ax.plot([a, b], [band_hi, band_hi], color=col, lw=1.6,
                solid_capstyle="butt", zorder=1)

    # Alignment swim-lane marks (per sample).
    for a in acts:
        an = a["payload"].get("action_name")
        if a["payload"].get("role") == "taxi" or an in (
                "acquire_projection", "fly_scan_prep", "write_dataset"):
            continue
        if a["payload"].get("role") == "fly_scan":
            continue
        x, y = secs(a["sampled_at"]), LANE_Y[a["step_kind"]]
        ax.scatter([x], [y], marker=LANE_MARKER[a["step_kind"]], s=34,
                   color=LANE_COLOR[a["step_kind"]], zorder=3, edgecolors="white",
                   linewidths=0.5)
        if a["step_kind"] == "check":
            # Alternate the label offset by iteration parity so adjacent
            # residuals (bands are only ~8 s apart) do not run together.
            dy = -10 if (a["iteration"] or 0) % 2 else -19
            ax.annotate(f"{a['payload']['actual']:.2f}", (x, y),
                        textcoords="offset points", xytext=(0, dy), ha="center",
                        fontsize=s.SIZE["small"], color=s.STATE)

    # Science projections. The interrupted projection on sample B has an
    # in-flight marker before the cursor and an ok marker after recovery.
    projs = [a for a in acts if a["payload"].get("action_name") == "acquire_projection"]
    y = LANE_Y["action"]
    inflight_list = [secs(a["sampled_at"]) for a in projs if a["result"] == "in_flight"]
    ok_times = sorted(secs(a["sampled_at"]) for a in projs if a["result"] == "ok")
    for t in ok_times:
        ghost = t > cursor
        ax.scatter([t], [y], marker="^", s=30, color=(s.MUTE if ghost else s.SUBINK),
                   alpha=(0.5 if ghost else 1.0), edgecolors="white",
                   linewidths=0.5, zorder=3)
    if inflight_list:
        inflight = inflight_list[0]
        ax.plot([inflight, cursor], [y, y], color=s.ALARM, lw=4.0, ls=(0, (0.9, 0.8)),
                dash_capstyle="butt", alpha=0.9, zorder=2)
        ax.scatter([inflight], [y], marker="^", s=46, color=s.ALARM,
                   edgecolors="white", linewidths=0.6, zorder=3)
        ax.annotate("projection 3:\nin flight", ((inflight + cursor) / 2, y),
                    textcoords="offset points", xytext=(0, 8), ha="center",
                    fontsize=s.SIZE["small"], color=s.ALARM, fontweight="bold",
                    linespacing=1.0)

    # Dataset writes on the output lane (ghosted if past the cursor).
    ax.axhline(Y_OUTPUT, color=s.RULE, lw=0.6, zorder=0)
    for a in acts:
        if a["payload"].get("action_name") != "write_dataset":
            continue
        x = secs(a["sampled_at"])
        ghost = x > cursor
        ax.scatter([x], [Y_OUTPUT], marker="p", s=46,
                   color=(s.MUTE if ghost else s.GOOD),
                   alpha=(0.6 if ghost else 0.9), edgecolors="white",
                   linewidths=0.5, zorder=3)

    # Fold-to-version cursor at the beam-loss instant.
    ax.axvline(cursor, color=s.ALARM, ls="--", lw=1.3, zorder=5)
    ax.text(cursor, Y_PHASE[1] + 0.12, "cursor: beam loss", color=s.ALARM,
            fontsize=s.SIZE["anno"], ha="center", va="bottom", fontweight="bold")

    # Folded-state readout card parked in the held band.
    def _row(text, color, weight="normal", size=s.SIZE["small"]):
        return TextArea(text, textprops={"color": color, "fontweight": weight,
                                         "fontsize": size})

    readout = VPacker(pad=0, sep=4.0, align="left", children=[
        _row("Folded state at cursor", s.ALARM, "bold", s.SIZE["anno"]),
        _row("sample: B mounted (robot)", s.INK),
        _row("alignment: converged (0.30 px)", s.INK),
        _row("projections: 2 done, #3 in flight", s.INK),
        _row("run: held by supervisor", s.INK),
        _row("fidelity: verified", s.INK),
    ])
    card = AnchoredOffsetbox(loc="center left", child=readout, pad=0.6, borderpad=0,
                             frameon=True, bbox_to_anchor=(0.845, 0.46),
                             bbox_transform=ax.transAxes)
    card.patch.set(boxstyle="round,pad=0,rounding_size=0.5", facecolor="white",
                   edgecolor=s.RULE, linewidth=1.0)
    card.set_zorder(6)
    ax.add_artist(card)

    yticks = [Y_OUTPUT] + list(LANE_LABEL) + [Y_PERMIT, Y_RUN, Y_ROBOT, Y_CUSTODY]
    ylabels = (["Output"] + [LANE_LABEL[k] for k in LANE_LABEL]
               + ["Beam permit", "Run", "Robot", "Sample"])
    ax.set_yticks(yticks)
    ax.set_yticklabels(ylabels, fontsize=s.SIZE["label"])
    ax.set_ylim(Y_OUTPUT - 0.7, Y_PHASE[1] + 0.5)
    # Reserve right-margin space for the folded-state readout card so it does
    # not overlap sample B's science swim-lanes.
    ax.set_xlim(-6, xmax + 46)
    ax.set_xlabel("time (s; synthetic spacing, see data/README.md)",
                  fontsize=s.SIZE["label"])
    ax.tick_params(axis="x", labelsize=s.SIZE["tick"])
    s.despine(ax, keep=("bottom",))
    s.title(ax, "Replay scrubber: a robot-loaded, two-sample run at APS 2-BM")

    legend = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor=s.OPERATOR,
               markersize=6.5, label="operator"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=s.AGENT,
               markersize=6.5, label="supervisor"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=s.STATE,
               markersize=6.5, label="robot mount/dismount"),
        Patch(facecolor=s.WARN_BG, edgecolor=s.WARN, label="iteration: open"),
        Patch(facecolor=s.GOOD_BG, edgecolor=s.GOOD, label="iteration: converged"),
        Line2D([0], [0], color=s.ALARM, lw=4.0, ls=(0, (0.9, 0.8)),
               dash_capstyle="butt", label="in-flight (open)"),
        Line2D([0], [0], color=s.GOOD, lw=3, label="beam permit OK"),
    ]
    ax.legend(handles=legend, loc="lower left", ncol=4, fontsize=s.SIZE["legend"],
              frameon=False, bbox_to_anchor=(0.0, -0.26), handletextpad=0.5,
              columnspacing=1.4)

    s.save(fig, "f1_scrubber")


if __name__ == "__main__":
    main()

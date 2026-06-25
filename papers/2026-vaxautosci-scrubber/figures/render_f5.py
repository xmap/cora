#!/usr/bin/env python3
"""Render Figure 5, the event-record substrate (the one architecture figure).

An append-only, totally ordered procedure stream; folding the prefix up to a
cursor reconstructs state. Three records carry what the four tasks need: each
event's envelope (who/what + position), the run-start payload (recipe expansion
+ content hash, feeding the fidelity badge), and the iteration-boundary events
(the converged verdict). Labeled "substrate, not contribution".

Full-width figure: rendered at the full text width.
Run: uv run --no-project --with matplotlib python figures/render_f5.py
"""

from __future__ import annotations

import _style as s
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def main() -> None:
    fig, ax = s.figure(s.FULL_WIDTH, 2.55)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7.4)
    ax.axis("off")

    ax.text(0.2, 7.05, "The event-record substrate", ha="left", va="center",
            fontsize=s.SIZE["title"], fontweight="bold", color=s.INK)
    ax.text(13.85, 7.05, "substrate, not contribution", ha="right", va="center",
            fontsize=s.SIZE["small"], style="italic", color=s.MUTE)

    labels = ["Registered", "Started", "Iter\nStarted", "Iter\nEnded", "Completed"]
    bw, bh, gap, x0, ymid = 1.5, 0.95, 0.18, 0.3, 3.05
    xs = [x0 + i * (bw + gap) for i in range(len(labels))]
    for x, lab in zip(xs, labels):
        ax.add_patch(
            FancyBboxPatch(
                (x, ymid), bw, bh, boxstyle="round,pad=0.02,rounding_size=0.08",
                linewidth=1.0, edgecolor=s.OPERATOR, facecolor="white",
            )
        )
        ax.text(x + bw / 2, ymid + bh / 2, lab, ha="center", va="center",
                fontsize=s.SIZE["anno"], color=s.INK)

    stream_right = xs[-1] + bw
    s.arrow(ax, (x0, ymid - 0.42), (stream_right, ymid - 0.42), color=s.RULE,
            lw=1.0, scale=9)
    ax.text((x0 + stream_right) / 2, ymid - 0.92,
            "append-only, totally ordered  ·  folding is deterministic",
            ha="center", va="center", fontsize=s.SIZE["small"], color=s.SUBINK)

    cur = xs[3] + bw + gap / 2
    ax.plot([cur, cur], [ymid - 0.2, ymid + bh + 0.5], color=s.ALARM, ls="--", lw=1.1)
    ax.text(cur, ymid + bh + 0.66, "cursor $t$", color=s.ALARM,
            fontsize=s.SIZE["small"], ha="center", fontweight="bold")

    state_x = 11.05
    s.card(ax, state_x, ymid - 0.06, 2.65, 1.2,
           "reconstructed\nstate at $t$\n(fold of $e_1\\ldots e_t$)", edge=s.STATE,
           face=s.PANEL, fontsize=s.SIZE["small"], weight="bold", tc=s.STATE)
    ax.add_patch(
        FancyArrowPatch(
            (cur, ymid + bh + 0.02), (state_x, ymid + 0.66), arrowstyle="-|>",
            mutation_scale=11, lw=1.3, color=s.STATE,
            connectionstyle="arc3,rad=-0.22", shrinkA=3, shrinkB=3,
        )
    )

    amber_cx = xs[1] + bw / 2
    green_cx = xs[3] + bw / 2
    s.card(ax, amber_cx - 1.5, 5.05, 3.0, 1.05,
           "run-start payload:\nexpansion + content hash (T4)", edge=s.WARN,
           fontsize=s.SIZE["small"])
    s.arrow(ax, (amber_cx, 5.05), (amber_cx, ymid + bh), color=s.WARN)
    s.card(ax, green_cx - 1.4, 5.05, 2.8, 1.05,
           "boundary event:\nconverged verdict (T3)", edge=s.GOOD,
           fontsize=s.SIZE["small"])
    s.arrow(ax, (green_cx, 5.05), (green_cx, ymid + bh), color=s.GOOD)
    s.card(ax, x0 - 0.15, 0.95, 3.4, 1.0,
           "each event's envelope:\nwho/what + position (T1, T2)", edge=s.OPERATOR,
           fontsize=s.SIZE["small"])
    s.arrow(ax, (xs[0] + bw / 2, ymid), (xs[0] + bw / 2, 1.95), color=s.OPERATOR)

    s.save(fig, "f5_substrate")


if __name__ == "__main__":
    main()

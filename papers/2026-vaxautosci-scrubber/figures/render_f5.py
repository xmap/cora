#!/usr/bin/env python3
"""Render Figure 5, the event-record substrate (the one architecture figure).

An append-only, totally ordered procedure stream; folding the prefix up to a
cursor reconstructs state. Each box is one event (e_1..e_5); the shaded prefix
e_1..e_t is what folds to the reconstructed state at the cursor. Three records
carry what the four tasks need: each event's envelope (who/what + position), the
run-start payload (recipe expansion + content hash, feeding the fidelity badge),
and the iteration-boundary events (the converged verdict). Labeled "substrate,
not contribution".

Full-width figure: rendered at the full text width.
Run: uv run --no-project --with matplotlib python figures/render_f5.py
"""

from __future__ import annotations

import _style as s
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


def main() -> None:
    fig, ax = s.figure(s.FULL_WIDTH, 2.95)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7.8)
    ax.axis("off")

    ax.text(0.2, 7.45, "The event-record substrate", ha="left", va="center",
            fontsize=s.SIZE["title"], fontweight="bold", color=s.INK)
    ax.text(13.85, 7.45, "substrate, not contribution", ha="right", va="center",
            fontsize=s.SIZE["small"], style="italic", color=s.MUTE)
    ax.text(0.2, 6.85,
            "Each box is one event; fold the prefix up to cursor $t$ to "
            "reconstruct the state at $t$.",
            ha="left", va="center", fontsize=s.SIZE["small"], color=s.SUBINK)

    labels = ["Registered", "Started", "Iter\nStarted", "Iter\nEnded", "Completed"]
    bw, bh, gap, x0, ymid = 1.5, 0.95, 0.18, 0.3, 3.45
    xs = [x0 + i * (bw + gap) for i in range(len(labels))]
    cur = xs[3] + bw + gap / 2  # cursor t, between Iter Ended (e_4) and Completed

    # Shaded prefix e_1..e_t: the events that fold to the reconstructed state.
    ax.add_patch(Rectangle((x0 - 0.12, ymid - 0.18), cur - (x0 - 0.12), bh + 0.36,
                           facecolor="#E6F2EF", edgecolor="none", zorder=0))
    ax.text((x0 - 0.12 + cur) / 2, ymid + bh + 0.30, "prefix folded to $t$",
            ha="center", va="center", fontsize=s.SIZE["small"], style="italic",
            color=s.STATE)

    for i, (x, lab) in enumerate(zip(xs, labels)):
        ax.add_patch(
            FancyBboxPatch(
                (x, ymid), bw, bh, boxstyle="round,pad=0.02,rounding_size=0.08",
                linewidth=1.0, edgecolor=s.OPERATOR, facecolor="white", zorder=2,
            )
        )
        ax.text(x + bw / 2, ymid + bh / 2, lab, ha="center", va="center",
                fontsize=s.SIZE["anno"], color=s.INK, zorder=3)
        ax.text(x + bw / 2, ymid - 0.32, f"$e_{i + 1}$", ha="center", va="center",
                fontsize=s.SIZE["small"], color=s.SUBINK)

    stream_right = xs[-1] + bw
    s.arrow(ax, (x0, ymid - 0.72), (stream_right, ymid - 0.72), color=s.RULE,
            lw=1.0, scale=9)
    ax.text((x0 + stream_right) / 2, ymid - 1.08, "append-only, totally ordered",
            ha="center", va="center", fontsize=s.SIZE["small"], color=s.SUBINK)

    ax.plot([cur, cur], [ymid - 0.18, ymid + bh + 0.30], color=s.ALARM, ls="--",
            lw=1.1, zorder=4)
    ax.text(cur + 0.12, ymid + bh + 0.46, "cursor $t$", color=s.ALARM,
            fontsize=s.SIZE["small"], ha="center", fontweight="bold")

    state_x = 11.05
    s.card(ax, state_x, ymid - 0.12, 2.65, 1.3,
           "reconstructed\nstate at $t$\n$=$ fold$(e_1\\ldots e_t)$", edge=s.STATE,
           face=s.PANEL, fontsize=s.SIZE["small"], weight="bold", tc=s.STATE)
    ax.add_patch(
        FancyArrowPatch(
            (cur, ymid + bh + 0.02), (state_x, ymid + 0.7), arrowstyle="-|>",
            mutation_scale=11, lw=1.3, color=s.STATE,
            connectionstyle="arc3,rad=-0.22", shrinkA=3, shrinkB=3,
        )
    )

    payload_cx = xs[1] + bw / 2
    verdict_cx = xs[3] + bw / 2
    s.card(ax, payload_cx - 1.5, 5.25, 3.0, 1.05,
           "run-start payload:\nexpansion + content hash (T4)", edge=s.WARN,
           fontsize=s.SIZE["small"])
    s.arrow(ax, (payload_cx, 5.25), (payload_cx, ymid + bh), color=s.WARN)
    s.card(ax, verdict_cx - 1.4, 5.25, 2.8, 1.05,
           "boundary event:\nconverged verdict (T3)", edge=s.GOOD,
           fontsize=s.SIZE["small"])
    s.arrow(ax, (verdict_cx, 5.25), (verdict_cx, ymid + bh), color=s.GOOD)
    s.card(ax, x0 - 0.15, 0.55, 3.4, 1.0,
           "each event's envelope:\nwho/what + position (T1, T2)", edge=s.OPERATOR,
           fontsize=s.SIZE["small"])
    s.arrow(ax, (xs[0] + bw / 2, ymid), (xs[0] + bw / 2, 1.55), color=s.OPERATOR)

    s.save(fig, "f5_substrate")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Render Figure 5, the event-record substrate (the one architecture figure).

An append-only, totally ordered procedure stream; folding the prefix up to a
cursor reconstructs state. Three records carry what the four tasks need: each
event's envelope (who/what + position), the run-start payload (recipe expansion
+ content hash, feeding the fidelity badge), and the iteration-boundary events
(the converged verdict). Labeled "substrate, not contribution".

Run: uv run --no-project --with matplotlib python figures/render_f5.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = Path(__file__).parent

C_EVENT = "#3B6EA5"
C_PAYLOAD = "#B8860B"
C_VERDICT = "#2E7D32"
C_STATE = "#2A9D8F"
C_BG = "#F4F6F8"


def _box(ax, x, y, w, h, text, ec, fc=C_BG, fontsize=6.6, weight="normal", tc="#222222"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.2, edgecolor=ec, facecolor=fc,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, color=tc, fontweight=weight)


def _arrow(ax, xy_from, xy_to, color="#666666", style="-|>", lw=1.2):
    ax.add_patch(
        FancyArrowPatch(xy_from, xy_to, arrowstyle=style, mutation_scale=10, lw=lw, color=color, shrinkA=1, shrinkB=1)
    )


def main() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 2.95))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7)
    ax.axis("off")

    labels = ["Registered", "Started", "Iter\nStarted", "Iter\nEnded", "Completed"]
    bw, bh, gap, x0, ymid = 1.5, 0.95, 0.16, 0.3, 3.3
    xs = [x0 + i * (bw + gap) for i in range(len(labels))]
    for x, lab in zip(xs, labels):
        ax.add_patch(
            FancyBboxPatch(
                (x, ymid), bw, bh, boxstyle="round,pad=0.02,rounding_size=0.06",
                linewidth=1.1, edgecolor=C_EVENT, facecolor="white",
            )
        )
        ax.text(x + bw / 2, ymid + bh / 2, lab, ha="center", va="center", fontsize=6.4, color="#222222")

    stream_right = xs[-1] + bw
    # Ordering axis under the stream.
    _arrow(ax, (x0, ymid - 0.45), (stream_right, ymid - 0.45), color="#999999", lw=1.0)
    ax.text(
        (x0 + stream_right) / 2, ymid - 0.95,
        "append-only, totally ordered  ·  folding is deterministic",
        ha="center", va="center", fontsize=6.4, color="#666666",
    )

    # Cursor after "Iter Ended"; fold the prefix to the reconstructed state.
    cur = xs[3] + bw + gap / 2
    ax.plot([cur, cur], [ymid - 0.2, ymid + bh + 0.55], color="#C0392B", ls="--", lw=1.2)
    ax.text(cur, ymid + bh + 0.72, "cursor $t$", color="#C0392B", fontsize=6.6, ha="center", fontweight="bold")

    state_x = 11.0
    _box(ax, state_x, ymid - 0.05, 2.7, 1.15, "reconstructed\nstate at $t$\n(fold of $e_1..e_t$)", ec=C_STATE, fontsize=6.6, weight="bold", tc=C_STATE)
    # Fold arrow curves above the stream so it does not cut through "Completed".
    ax.add_patch(
        FancyArrowPatch(
            (cur, ymid + bh + 0.05), (state_x, ymid + 0.62), arrowstyle="-|>",
            mutation_scale=12, lw=1.5, color=C_STATE,
            connectionstyle="arc3,rad=-0.22", shrinkA=3, shrinkB=3,
        )
    )

    # Three record callouts (separated so the two top boxes do not overlap).
    amber_cx = xs[1] + bw / 2
    green_cx = xs[3] + bw / 2
    _box(ax, amber_cx - 1.475, 5.2, 2.95, 1.1, "run-start payload:\nexpansion + content hash (T4)", ec=C_PAYLOAD, fontsize=6.0)
    _arrow(ax, (amber_cx, 5.2), (amber_cx, ymid + bh), color=C_PAYLOAD)
    _box(ax, green_cx - 1.375, 5.2, 2.75, 1.1, "boundary event:\nconverged verdict (T3)", ec=C_VERDICT, fontsize=6.0)
    _arrow(ax, (green_cx, 5.2), (green_cx, ymid + bh), color=C_VERDICT)
    # envelope (below Registered).
    _box(ax, x0 - 0.2, 1.05, 3.4, 1.0, "each event's envelope:\nwho/what + position (T1, T2)", ec=C_EVENT, fontsize=6.0)
    _arrow(ax, (xs[0] + bw / 2, ymid), (xs[0] + bw / 2, 2.05), color=C_EVENT)

    ax.text(13.85, 6.7, "substrate, not contribution", ha="right", va="center", fontsize=6.4, style="italic", color="#888888")

    fig.savefig(HERE / "f5_substrate.pdf", bbox_inches="tight", pad_inches=0.08)
    fig.savefig(HERE / "f5_substrate.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    print("wrote f5_substrate.pdf / .png")


if __name__ == "__main__":
    main()

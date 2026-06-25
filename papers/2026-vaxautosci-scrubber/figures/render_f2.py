#!/usr/bin/env python3
"""Render Figure 2, the fidelity badge mechanism.

A schematic of the check the badge runs at the cursor: the content-addressed
hash recorded with the run (in the run-start payload) is compared against the
hash recomputed from the state reconstructed by folding to the cursor; a match
yields "verified", a mismatch would read "altered". The append-only store means
the recorded side cannot have changed after the run.

The short digest is a real content hash of data/lights_out_run.json (illustrative,
not the production verify-hash, which lives on the conduct path).

Run: uv run --no-project --with matplotlib python figures/render_f2.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = Path(__file__).parent
RUN = json.loads((HERE.parent / "data" / "lights_out_run.json").read_text())

C_REC = "#3B6EA5"
C_REPLAY = "#6B7280"
C_OK = "#2E7D32"
C_BG = "#F4F6F8"


def _short_digest() -> str:
    blob = json.dumps(RUN["activities"], sort_keys=True).encode()
    h = hashlib.sha256(blob).hexdigest()
    return f"{h[:4]}…{h[-4:]}"


def _box(ax, x, y, w, h, text, ec, fc=C_BG, fontsize=7.2, weight="normal", tc="#222222"):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.2, edgecolor=ec, facecolor=fc, mutation_aspect=1,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize, color=tc, fontweight=weight)


def _arrow(ax, xy_from, xy_to, color="#555555"):
    ax.add_patch(
        FancyArrowPatch(
            xy_from, xy_to, arrowstyle="-|>", mutation_scale=11,
            lw=1.3, color=color, shrinkA=2, shrinkB=2,
        )
    )


def main() -> None:
    digest = _short_digest()
    fig, ax = plt.subplots(figsize=(4.9, 2.25))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    _box(
        ax, 0.3, 3.7, 4.3, 1.7,
        f"recorded expansion\n(run-start payload)\ncontent hash  {digest}",
        ec=C_REC,
    )
    _box(
        ax, 5.4, 3.7, 4.3, 1.7,
        f"replayed state at cursor\n(fold to $t$, recompute)\ncontent hash  {digest}",
        ec=C_REPLAY,
    )

    # Compare node.
    _box(ax, 4.05, 2.0, 1.9, 1.0, "compare\n=", ec="#888888", fc="white", fontsize=8, weight="bold")
    _arrow(ax, (2.45, 3.7), (4.6, 3.0), color=C_REC)
    _arrow(ax, (7.55, 3.7), (5.4, 3.0), color=C_REPLAY)

    # Verdict badge.
    _box(ax, 3.0, 0.45, 4.0, 1.05, "fidelity: verified", ec=C_OK, fc="#E7F2E8", fontsize=9, weight="bold", tc=C_OK)
    _arrow(ax, (5.0, 2.0), (5.0, 1.5), color=C_OK)

    ax.text(
        5.0, 5.75, "Fidelity check at the cursor", ha="center", va="center",
        fontsize=9, fontweight="bold", color="#222222",
    )
    ax.text(
        5.0, -0.05,
        "append-only store: the recorded hash cannot have changed after the run; "
        "a mismatch would read “altered”",
        ha="center", va="center", fontsize=6.0, color="#666666",
    )

    fig.savefig(HERE / "f2_fidelity.pdf", bbox_inches="tight", pad_inches=0.08)
    fig.savefig(HERE / "f2_fidelity.png", dpi=200, bbox_inches="tight", pad_inches=0.08)
    print("wrote f2_fidelity.pdf / .png  (digest", digest + ")")


if __name__ == "__main__":
    main()

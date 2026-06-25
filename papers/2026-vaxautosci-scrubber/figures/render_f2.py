#!/usr/bin/env python3
"""Render Figure 2, the fidelity badge mechanism.

A schematic of the check the badge runs at the cursor: the content-addressed
hash recorded with the run (in the run-start payload) is compared against the
hash recomputed from the state reconstructed by folding to the cursor; a match
yields "verified", a mismatch would read "altered". The append-only store means
the recorded side cannot have changed after the run.

The short digest is a real content hash of data/lights_out_run.json (illustrative,
not the production verify-hash, which lives on the conduct path).

Single-column figure: rendered at one column width.
Run: uv run --no-project --with matplotlib python figures/render_f2.py
"""

from __future__ import annotations

import hashlib
import json

import _style as s

HERE = s.HERE
RUN = json.loads((HERE.parent / "data" / "lights_out_run.json").read_text())


def _short_digest() -> str:
    blob = json.dumps(RUN["activities"], sort_keys=True).encode()
    h = hashlib.sha256(blob).hexdigest()
    return f"{h[:4]}…{h[-4:]}"


def main() -> None:
    digest = _short_digest()
    fig, ax = s.figure(s.COL_WIDTH, 2.15)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 7.2)
    ax.axis("off")

    s.card(
        ax, 0.15, 4.35, 4.55, 1.7,
        f"recorded expansion\nrun-start payload\nhash  {digest}",
        edge=s.OPERATOR,
    )
    s.card(
        ax, 5.30, 4.35, 4.55, 1.7,
        f"replayed at cursor\nfold to $t$, recompute\nhash  {digest}",
        edge=s.SUBINK,
    )

    s.card(ax, 3.95, 2.55, 2.10, 1.05, "compare\n=", edge=s.MUTE, face="white",
           fontsize=s.SIZE["label"], weight="bold")
    s.arrow(ax, (2.30, 4.35), (4.45, 3.60), color=s.OPERATOR, rad=0.05)
    s.arrow(ax, (7.55, 4.35), (5.55, 3.60), color=s.SUBINK, rad=-0.05)

    s.pill(ax, 2.85, 0.85, 4.30, 1.05, "fidelity: verified", edge=s.GOOD,
           face=s.GOOD_BG, tc=s.GOOD, fontsize=s.SIZE["title"])
    s.arrow(ax, (5.0, 2.55), (5.0, 1.92), color=s.GOOD)

    ax.text(0.15, 6.85, "Fidelity check at the cursor", ha="left", va="center",
            fontsize=s.SIZE["title"], fontweight="bold", color=s.INK)
    ax.text(5.0, 0.10,
            "append-only store: the recorded hash cannot change after\n"
            "the run; a mismatch would read “altered”",
            ha="center", va="center", fontsize=s.SIZE["small"], color=s.SUBINK,
            linespacing=1.3)

    s.save(fig, "f2_fidelity")


if __name__ == "__main__":
    main()

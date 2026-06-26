"""Shared visual language for the paper figures.

One type scale and one palette drive every figure, so a given point size is the
same physical size on the page wherever it appears. Each figure is also rendered
at its final on-page width (full text width, or one column), so LaTeX places it
at scale ~1.0 and the type stays consistent across the paper.

Import and call install() at the top of every render_*.py, then build figures
with figure() and finish with save().

Render: uv run --no-project --with matplotlib python figures/render_fX.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib import font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = Path(__file__).parent

# On-page widths in inches, from vgtc.cls (textwidth 7.125in, columnsep 0.17in).
# Rendering at these widths keeps a point a point everywhere on the page.
FULL_WIDTH = 7.125
COL_WIDTH = (7.125 - 0.17) / 2  # 3.4775

# Type scale in points. Because figures render at final width, these are the
# sizes the reader sees on the page; reuse them, do not invent new ones.
SIZE = {
    "title": 9.0,
    "subtitle": 7.2,
    "label": 7.5,
    "tick": 7.0,
    "anno": 7.0,
    "small": 6.2,
    "legend": 7.0,
    "mono": 7.0,
}

# Harmonized palette: neutral structure, a small set of tuned accents that all
# sit at a similar saturation and value so the figures read as one family.
INK = "#1F2933"      # primary text and strong marks
SUBINK = "#52606D"   # secondary text, axis labels
MUTE = "#9AA5B1"     # tertiary text, ghosted / not-yet-happened
RULE = "#D2D7DD"     # axes, baselines, light structure
PANEL = "#F4F6F8"    # subtle panel / card fill
HELD = "#EEF1F4"     # shaded "held" band

OPERATOR = "#3B6FB6"  # human-driven
AGENT = "#7A5AC2"     # agent / supervisor (distinct from the alarm hue)
GOOD = "#2E9E6B"      # converged, verified, closed
WARN = "#E0A21B"      # open, not-yet-converged
ALARM = "#E2533B"     # cursor, beam loss, in-flight without outcome
STATE = "#0E9488"     # reconstructed state, measured metric

GOOD_BG = "#E8F4EE"
WARN_BG = "#FBF1DC"
ALARM_BG = "#FBEDE9"

_INSTALLED = False


def install() -> None:
    """Register the figure font and apply shared rcParams (idempotent)."""
    global _INSTALLED
    if _INSTALLED:
        return
    _candidates = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf",
    ]
    for path in _candidates:
        if Path(path).exists():
            try:
                fm.fontManager.addfont(path)
            except Exception:  # noqa: BLE001 - missing/odd font is non-fatal
                pass

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
            "font.size": SIZE["anno"],
            "text.color": INK,
            "axes.edgecolor": RULE,
            "axes.labelcolor": SUBINK,
            "axes.linewidth": 0.8,
            "axes.titlesize": SIZE["title"],
            "axes.titlecolor": INK,
            "axes.titleweight": "bold",
            "xtick.color": SUBINK,
            "ytick.color": SUBINK,
            "xtick.labelsize": SIZE["tick"],
            "ytick.labelsize": SIZE["tick"],
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.major.size": 3.0,
            "ytick.major.size": 0.0,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.fontsize": SIZE["legend"],
            "legend.frameon": False,
            "legend.handletextpad": 0.5,
            "legend.columnspacing": 1.2,
            "lines.solid_capstyle": "round",
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "mathtext.fontset": "stixsans",
        }
    )
    _INSTALLED = True


def _tighten(fig) -> None:
    """Minimal, symmetric padding so the saved canvas width equals the figsize."""
    eng = fig.get_layout_engine()
    if eng is not None:
        eng.set(w_pad=0.02, h_pad=0.02, wspace=0.02, hspace=0.04)


def figure(width: float, height: float):
    """A figure + axes at the given on-page width (inches).

    Constrained layout packs decorations inside the fixed figsize, so the saved
    canvas width equals `width` and LaTeX places the figure at scale 1.0.
    """
    install()
    return plt.subplots(figsize=(width, height), layout="constrained")


def despine(ax, keep=("bottom",)) -> None:
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(side in keep)


def title(ax, text: str, subtitle: str | None = None) -> None:
    """Left-aligned figure title with an optional muted subtitle."""
    ax.set_title(text, loc="left", fontsize=SIZE["title"], fontweight="bold",
                 color=INK, pad=8)
    if subtitle:
        ax.set_title(subtitle, loc="right", fontsize=SIZE["subtitle"],
                     fontweight="normal", color=MUTE, pad=8)


def card(ax, x, y, w, h, text, *, edge, face=PANEL, fontsize=None,
         weight="normal", tc=INK, rounding=0.10, lw=1.0, align="center"):
    """A flat rounded card with a thin border and centered text."""
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle=f"round,pad=0.02,rounding_size={rounding}",
            linewidth=lw, edgecolor=edge, facecolor=face, mutation_aspect=1,
        )
    )
    tx = x + w / 2 if align == "center" else x + 0.12
    ax.text(tx, y + h / 2, text, ha="center" if align == "center" else "left",
            va="center", fontsize=fontsize or SIZE["anno"], color=tc,
            fontweight=weight, linespacing=1.15)


def pill(ax, x, y, w, h, text, *, edge, face, tc, fontsize=None, weight="bold"):
    """A high-rounding badge for a verdict."""
    card(ax, x, y, w, h, text, edge=edge, face=face, tc=tc,
         fontsize=fontsize or SIZE["anno"], weight=weight, rounding=h / 2,
         lw=1.1)


def arrow(ax, xy_from, xy_to, *, color=SUBINK, lw=1.1, style="-|>", scale=10,
          rad=0.0, shrink=2.0):
    ax.add_patch(
        FancyArrowPatch(
            xy_from, xy_to, arrowstyle=style, mutation_scale=scale, lw=lw,
            color=color, shrinkA=shrink, shrinkB=shrink,
            connectionstyle=f"arc3,rad={rad}",
        )
    )


def save(fig, stem: str) -> None:
    """Write <stem>.pdf and <stem>.png at the figure's exact width.

    Saving the full canvas (no tight crop) keeps the natural PDF width equal to
    the figsize, so a point is the same physical size on the page in every figure.
    """
    _tighten(fig)
    for ext in ("pdf", "png"):
        out = HERE / f"{stem}.{ext}"
        fig.savefig(out, bbox_inches=None, pad_inches=0.0)
        print(f"wrote {out}")
    plt.close(fig)

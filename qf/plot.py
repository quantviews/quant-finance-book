"""Единый стиль графиков книги (matplotlib).

    from qf import plot
    plot.use_book_style()
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager

FONTS = Path(__file__).resolve().parents[1] / "fonts"

# Палитра из _brand.yaml + дополнительные контрастные цвета для рядов.
NAVY = "#23415F"
BLUE = "#34699A"
GREY = "#6B7280"
ORANGE = "#C8702A"
GREEN = "#3F8F5B"
RED = "#B8412E"
PALETTE = [BLUE, ORANGE, GREEN, RED, NAVY, GREY]


def use_book_style() -> None:
    """Шрифт IBM Plex Sans, палитра книги, аккуратные оси."""
    for f in (FONTS / "ibm-plex-sans").glob("*.ttf"):
        font_manager.fontManager.addfont(str(f))
    mpl.rcParams.update(
        {
            "font.family": "IBM Plex Sans",
            "font.size": 10,
            "axes.titlesize": 11,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.labelsize": 10,
            "axes.labelcolor": "#333333",
            "axes.edgecolor": "#999999",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": "#E5E7EB",
            "grid.linewidth": 0.8,
            "axes.prop_cycle": mpl.cycler(color=PALETTE),
            "lines.linewidth": 1.4,
            "legend.frameon": False,
            "figure.figsize": (7, 3.6),
            "figure.dpi": 110,
            "savefig.bbox": "tight",
            "axes.formatter.use_locale": False,
            "axes.unicode_minus": True,
        }
    )

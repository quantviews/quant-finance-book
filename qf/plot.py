"""Единый стиль графиков книги (matplotlib).

Ориентир – графики Kieran Healy («Data Visualization»): узкий шрифт без засечек,
никаких рамок и засечек на осях, лёгкая сетка, заголовок слева, подпись
источника под графиком.

    from qf import plot
    plot.use_book_style()
    ax = df.plot()
    plot.source(ax, "Московская биржа")
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager

FONTS = Path(__file__).resolve().parents[1] / "fonts"
FONT = "IBM Plex Sans Condensed"

# Палитра из _brand.yaml + дополнительные контрастные цвета для рядов.
NAVY = "#23415F"
BLUE = "#34699A"
GREY = "#6B7280"
ORANGE = "#C8702A"
GREEN = "#3F8F5B"
RED = "#B8412E"
PALETTE = [BLUE, ORANGE, GREEN, RED, NAVY, GREY]

TEXT = "#374151"
LIGHT = "#6B7280"


def use_book_style() -> None:
    """Применить стиль книги ко всем последующим графикам."""
    for folder in ("ibm-plex-sans-condensed", "ibm-plex-sans"):
        for f in (FONTS / folder).glob("*.ttf"):
            font_manager.fontManager.addfont(str(f))
    mpl.rcParams.update(
        {
            "font.family": FONT,
            "font.size": 8.5,
            "text.color": TEXT,
            # заголовки
            "axes.titlesize": 10,
            "axes.titleweight": "semibold",
            "axes.titlelocation": "left",
            "axes.titlepad": 10,
            "axes.labelsize": 8.5,
            "axes.labelcolor": LIGHT,
            # оси: без рамки и засечек, лёгкая сетка под данными
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.spines.bottom": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": "#E3E6EA",
            "grid.linewidth": 0.6,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "xtick.major.pad": 4,
            "ytick.major.pad": 4,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "xtick.color": LIGHT,
            "ytick.color": LIGHT,
            # ряды и легенда
            "axes.prop_cycle": mpl.cycler(color=PALETTE),
            "lines.linewidth": 1.2,
            "lines.markersize": 4,
            "legend.frameon": False,
            "legend.fontsize": 8,
            "legend.handlelength": 1.6,
            # размеры: широкие невысокие графики
            "figure.figsize": (6.5, 3.2),
            "figure.dpi": 110,
            "figure.facecolor": "white",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
            "date.autoformatter.year": "%Y",
            "axes.formatter.use_locale": False,
            "axes.unicode_minus": True,
        }
    )


def source(ax, text: str, prefix: str = "Источник: ", offset: float = 20) -> None:
    """Подпись источника данных под графиком, слева.

    offset – отступ вниз от оси в пунктах (увеличьте, если есть подпись оси X).
    """
    ax.annotate(
        prefix + text,
        xy=(0, 0),
        xycoords="axes fraction",
        xytext=(0, -offset),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=7.5,
        color=LIGHT,
    )

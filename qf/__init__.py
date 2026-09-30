"""Вспомогательный модуль книги «Количественные финансы».

    from qf import data
    prices = data.load_stocks(["SBER", "GAZP"])
"""

from . import data, plot

__all__ = ["data", "plot"]

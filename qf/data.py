"""Загрузка учебных данных книги.

Все функции читают файлы из папки data/ в корне книги и возвращают
pandas.DataFrame (или polars.DataFrame при backend="polars").
Состав файлов описан в data/README.md.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Literal

import pandas as pd
import polars as pl

DATA_DIR = Path(os.environ.get("QF_DATA", Path(__file__).resolve().parents[1] / "data"))
FULL_DATA_DIR = Path(
    os.environ.get("QF_FULL_DATA", Path(__file__).resolve().parents[1] / "_data_full")
)

Backend = Literal["pandas", "polars"]


def _as_list(x: str | Iterable[str] | None) -> list[str] | None:
    if x is None:
        return None
    return [x] if isinstance(x, str) else list(x)


def _read(
    name: str,
    tickers=None,
    start=None,
    end=None,
    columns=None,
    backend: Backend = "pandas",
    date_col: str = "date",
    root: Path | None = None,
):
    path = (root or DATA_DIR) / name
    if not path.exists():
        raise FileNotFoundError(
            f"Нет файла {path}. Скачайте данные книги (см. data/README.md) "
            "или укажите папку в переменной окружения QF_DATA."
        )
    lf = pl.scan_parquet(path)
    tickers = _as_list(tickers)
    if tickers is not None:
        lf = lf.filter(pl.col("ticker").is_in(tickers))
    if start is not None:
        lf = lf.filter(pl.col(date_col) >= pd.Timestamp(start).date())
    if end is not None:
        lf = lf.filter(pl.col(date_col) <= pd.Timestamp(end).date())
    if columns is not None:
        keep = [c for c in ("date", "ticker") if c in lf.collect_schema().names()]
        lf = lf.select(keep + [c for c in columns if c not in keep])
    df = lf.collect()
    if backend == "polars":
        return df
    out = df.to_pandas()
    for c in out.columns:
        if c == date_col or c.endswith("date"):
            out[c] = pd.to_datetime(out[c])
    return out


def load_stocks(tickers=None, start=None, end=None, columns=None, backend: Backend = "pandas"):
    """Дневные данные акций в «длинном» формате: одна строка = (date, ticker).

    Колонки: open, high, low, close (с поправкой на сплиты), waprice, volume,
    value_rub (оборот), adj_close (с поправкой на дивиденды и сплиты),
    shares (число акций), market_cap (капитализация, руб.).
    """
    return _read("stocks.parquet", tickers, start, end, columns, backend)


def load_prices(tickers=None, start=None, end=None, field: str = "adj_close") -> pd.DataFrame:
    """Цены в «широком» формате: даты в строках, тикеры в столбцах."""
    df = load_stocks(tickers, start, end, columns=[field])
    return df.pivot(index="date", columns="ticker", values=field).sort_index()


def load_stocks_raw(tickers=None, start=None, end=None, backend: Backend = "pandas"):
    """Сырые цены ISS (без поправок) для бумаг со сплитами и переименованиями."""
    return _read("stocks_raw.parquet", tickers, start, end, None, backend)


def load_index(tickers="IMOEX", start=None, end=None, backend: Backend = "pandas"):
    """Индексы MOEX: IMOEX, MCFTR, RTSI, RGBI, RGBITR, RUCBTRNS, отраслевые MOEX**."""
    return _read("indexes.parquet", tickers, start, end, None, backend)


def load_dividends(tickers=None, backend: Backend = "pandas"):
    """Дивиденды: ticker, closing_date (дата закрытия реестра), year, period_type, dividend_value."""
    return _read("dividends.parquet", tickers, backend=backend, date_col="closing_date")


def load_key_rate(backend: Backend = "pandas"):
    """Ключевая ставка Банка России, % годовых, на даты изменения."""
    return _read("key_rate.parquet", backend=backend)


def load_ruonia(start=None, end=None, backend: Backend = "pandas"):
    """Ставка RUONIA, % годовых."""
    return _read("ruonia.parquet", start=start, end=end, backend=backend)


def load_zcyc(start=None, end=None, backend: Backend = "pandas"):
    """Кривая бескупонной доходности ОФЗ: date, period (лет), value (% годовых)."""
    return _read("zcyc.parquet", start=start, end=end, backend=backend)


def load_reference(name: Literal["sectors", "splits", "renames", "delisted"]) -> pd.DataFrame:
    """Справочники: отрасли, сплиты, переименования, снятые с торгов бумаги."""
    return pd.read_csv(DATA_DIR / f"{name}.csv")


def load_shares_full(start=None, end=None, board: str | None = "TQBR", backend: Backend = "pandas"):
    """Полная история рынка акций MOEX (все бумаги, поля ISS) из отдельного архива.

    board – режим торгов (TQBR – основной режим для акций; None – все режимы).
    """
    root = FULL_DATA_DIR / "shares"
    if not root.exists():
        raise FileNotFoundError(
            f"Нет папки {root}. Скачайте архив с полной историей (см. data/README.md) "
            "и укажите путь в переменной окружения QF_FULL_DATA."
        )
    lf = pl.scan_parquet(root / "**" / "*.parquet", hive_partitioning=True)
    if board is not None:
        lf = lf.filter(pl.col("BOARDID") == board)
    if start is not None:
        lf = lf.filter(pl.col("date") >= pd.Timestamp(start).date())
    if end is not None:
        lf = lf.filter(pl.col("date") <= pd.Timestamp(end).date())
    df = lf.drop("year", strict=False).collect()
    return df if backend == "polars" else df.to_pandas()

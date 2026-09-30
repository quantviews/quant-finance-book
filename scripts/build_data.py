"""Сборка снимка данных для книги из хранилища moexutils.

Запускается автором книги, а не студентами: нужен пакет moexutils
и доступ к его хранилищу (PostgreSQL + Parquet в MOEX_DATA_ROOT).

    set MOEX_DATA_ROOT=F:\\moex-data
    python scripts/build_data.py            # базовый снимок -> data/
    python scripts/build_data.py --full     # + полная история рынка акций -> _data_full/

Базовый снимок (data/, хранится в git, ~12 МБ):
    stocks.parquet        ~100 акций рабочего набора, цены с поправкой на сплиты,
                          adj_close (дивиденды + сплиты), капитализация
    stocks_raw.parquet    сырые цены ISS для примеров сплитов и переименований
    indexes.parquet       индексы MOEX (IMOEX, MCFTR, RGBITR, отраслевые и др.)
    dividends.parquet     история дивидендов (закрытияреестров.рф)
    key_rate.parquet      ключевая ставка ЦБ
    ruonia.parquet        ставка RUONIA
    zcyc.parquet          кривая бескупонной доходности ОФЗ (КБД)
    sectors.csv, splits.csv, renames.csv, delisted.csv – справочники

Полная история (_data_full/, раздаётся студентам архивом):
    shares/year=YYYY/*.parquet   все бумаги рынка акций MOEX с 1997 г., все режимы, поля ISS
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import polars as pl
from moexutils import lake, rates, stocks

BOOK = Path(__file__).resolve().parents[1]
MOEXUTILS = Path(stocks.__file__).resolve().parents[1]
DIVIDENDS = MOEXUTILS.parent / "dividends" / "data"

INDEXES = [
    "IMOEX", "MCFTR", "MCFTRR", "RTSI", "MOEXBC",          # рынок акций
    "RGBI", "RGBITR", "RUCBTRNS",                          # облигации
    "MOEXOG", "MOEXFN", "MOEXMM", "MOEXEU", "MOEXTL",      # отрасли
    "MOEXCH", "MOEXCN", "MOEXTN", "MOEXIT", "MOEXRE",
]
# Бумаги со сплитами и переименованиями – для главы о подготовке данных.
RAW_EXAMPLES = ["GMKN", "TRNFP", "VTBR", "PHOR", "IRAO", "T", "TCSG", "YNDX", "YDEX"]


def write(df: pl.DataFrame, name: str, out: Path) -> None:
    path = out / name
    df.write_parquet(path, compression="zstd", compression_level=19, statistics=True)
    print(f"{name:22s} {df.height:>9,d} строк  {path.stat().st_size / 1e6:6.2f} МБ")


def build_core(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)

    s = stocks.read_stocks(merge_renames=True, split_adjusted=True)
    s = s.drop([c for c in ("source_ticker",) if c in s.columns]).sort("ticker", "date")
    write(s, "stocks.parquet", out)

    raw = stocks.read_stocks(tickers=RAW_EXAMPLES, merge_renames=False, split_adjusted=False)
    write(raw.sort("ticker", "date"), "stocks_raw.parquet", out)

    idx = lake.query(
        f"""select date, SECID as ticker, CLOSE as close, VALUE as value_rub
            from lake.indexes_all
            where SECID in ({", ".join(repr(t) for t in INDEXES)})
            order by ticker, date"""
    )
    write(idx, "indexes.parquet", out)

    divs = []
    for f in sorted(DIVIDENDS.glob("*.csv")):
        d = pl.read_csv(f, try_parse_dates=True).with_columns(ticker=pl.lit(f.stem))
        divs.append(d.select("ticker", pl.all().exclude("ticker")))
    write(pl.concat(divs, how="diagonal_relaxed").sort("ticker", "closing_date"),
          "dividends.parquet", out)

    kr = pl.read_csv(MOEXUTILS / "metadata" / "key_rate.csv", try_parse_dates=True)
    write(kr, "key_rate.parquet", out)
    write(rates.read_ruonia(), "ruonia.parquet", out)
    write(lake.query("select * from lake.zcyc_yields order by date, period"), "zcyc.parquet", out)

    for name in ("sectors", "splits", "renames", "delisted"):
        shutil.copy(MOEXUTILS / "metadata" / f"{name}.csv", out / f"{name}.csv")

    return {"stocks_last_date": str(s["date"].max()), "tickers": s["ticker"].n_unique()}


def build_full(out: Path) -> None:
    target = out / "shares"
    if target.exists():
        shutil.rmtree(target)
    years = lake.query("select distinct year(date) as y from lake.shares order by 1")["y"]
    for y in years:
        df = lake.query(f"select * from lake.shares where year(date) = {y} order by SECID, date")
        part = target / f"year={y}"
        part.mkdir(parents=True)
        df.write_parquet(part / "part-0.parquet", compression="zstd", compression_level=19)
    shutil.copy(BOOK / "data" / "README.md", out / "README.md")
    size = sum(p.stat().st_size for p in target.rglob("*.parquet")) / 1e6
    print(f"shares (весь рынок)    {len(years)} лет, {size:.0f} МБ -> {target}")


def build_rfsd(out: Path) -> None:
    """Отчётность компаний (RFSD) – из соседнего проекта rfsd (../rfsd)."""
    try:
        from rfsd import export
    except ImportError:
        sys.exit("Нет пакета rfsd: установите его из ../rfsd (pip install -e ../rfsd).")
    export.to_book(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="выгрузить также всю историю рынка акций")
    ap.add_argument("--rfsd", action="store_true", help="выгрузить также данные RFSD из проекта rfsd")
    ap.add_argument("--rfsd-only", action="store_true",
                    help="только RFSD, не пересобирая данные биржи (числа в главах 2–4 не изменятся)")
    args = ap.parse_args()

    if args.rfsd_only:
        build_rfsd(BOOK / "data")
        return
    if args.rfsd:
        build_rfsd(BOOK / "data")
    info = build_core(BOOK / "data")
    info["built"] = dt.date.today().isoformat()
    (BOOK / "data" / "snapshot.json").write_text(json.dumps(info, ensure_ascii=False, indent=2))
    if args.full:
        build_full(BOOK / "_data_full")


if __name__ == "__main__":
    main()

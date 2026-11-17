"""Выгрузить исходный снимок занятия 3 из moexutils. Запускает только автор курса.

Запуск из корня книги (нужны moexutils и MOEX_DATA_ROOT):
    set MOEX_DATA_ROOT=F:\moex-data
    python lessons/03-returns-risk/export_source.py

Результат: data/stocks-source.parquet, data/index-source.parquet, data/ruonia-source.parquet,
data/source.json. Студентам этот шаг не нужен: build_materials.py работает только с этими файлами.
"""
from pathlib import Path
import datetime as dt
import json

import polars as pl
from moexutils import rates, stocks

HERE = Path(__file__).resolve().parent
START, END = "2015-01-01", "2026-11-16"
# Акции, распределённые между студентами (занятие 2), и SBER для общих примеров.
TICKERS = ["AFLT", "ALRS", "BSPB", "CHMF", "FEES", "GAZP", "GMKN", "HYDR", "IRAO", "LKOH",
           "MAGN", "MOEX", "MTSS", "NLMK", "NVTK", "PHOR", "PIKK", "PLZL", "ROSN", "RUAL",
           "SBERP", "SIBN", "SNGS", "TATN", "TRNFP", "SBER"]
COLS = ["date", "ticker", "close", "adj_close"]

s = stocks.read_stocks(tickers=TICKERS, start=START, end=END, merge_renames=True, split_adjusted=True)
s = s.select(COLS)
missing = sorted(set(TICKERS) - set(s["ticker"].unique()))
# Бумаг, которых нет в хранилище moexutils (SIBN), загружаем из ISS и корректируем тем же
# методом moexutils (дивиденды из проекта dividends), не записывая в хранилище.
extra = []
for t in missing:
    raw = stocks.fetch_stock(t, START, END)
    enriched, skipped = stocks.enrich(raw)
    print(t, "из ISS:", enriched.height, "строк; отброшено дивидендов:", skipped)
    extra.append(enriched.select(COLS))
s = pl.concat([s, *extra]).sort("ticker", "date")

# Дивиденды GMKN, PLZL, TRNFP до сплита записаны в проекте dividends в расчёте на акцию ПОСЛЕ
# сплита. moexutils.adj_close сначала делит их на сырую цену до сплита и получает доходность
# в 10–100 раз меньше (например, GMKN 2022: 11,66 / 22 000 ≈ 0,05%). Для занятия пересчитываем
# adj_close от сплит-скорректированного close (он уже в s), без повторного учёта сплита.
RESTATED = ["GMKN", "PLZL", "TRNFP"]
other_splits = stocks.load_splits().filter(~pl.col("ticker").is_in(RESTATED))
fixed = []
for t in RESTATED:
    sub = s.filter(pl.col("ticker") == t).select("date", "ticker", "close")
    out, skipped = stocks.adj_close(sub, stocks.load_dividends(t), other_splits)
    print(t, "adj_close пересчитан от сплит-скорректированной цены; отброшено:", skipped)
    fixed.append(out.select(COLS))
s = pl.concat([s.filter(~pl.col("ticker").is_in(RESTATED)), *fixed]).sort("ticker", "date")
assert set(s["ticker"].unique()) == set(TICKERS), "не все тикеры выгружены"
s.write_parquet(HERE / "data" / "stocks-source.parquet")

idx = pl.concat([stocks.read_index(t, START, END).select("date", "ticker", "close") for t in ["IMOEX", "MCFTR"]])
idx.write_parquet(HERE / "data" / "index-source.parquet")

ru = rates.read_ruonia().select("date", "rate").filter(pl.col("date") >= pl.date(2014, 12, 1))
ru.write_parquet(HERE / "data" / "ruonia-source.parquet")

info = {"source": "moexutils, MOEX ISS and dividend adjustments",
        "exported": str(dt.date.today()), "requested": [START, END],
        "from_iss_not_lake": missing,
        "stocks_last": str(s["date"].max()), "index_last": str(idx["date"].max()),
        "ruonia": {"source": "Bank of Russia RUONIA via moexutils lake",
                   "first": str(ru["date"].min()), "last": str(ru["date"].max())}}
(HERE / "data" / "source.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(info, ensure_ascii=False, indent=2))
print(s.group_by("ticker").agg(pl.col("date").min().alias("first"), pl.col("date").max().alias("last"),
                               pl.len().alias("n")).sort("ticker"))

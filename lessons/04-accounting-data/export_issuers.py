"""Выгрузить из полного RFSD отчётность эмитентов акций курса (только автор курса).

Запуск из корня книги (нужна локальная копия RFSD, проект ../rfsd, RFSD_DATA_ROOT):
    python lessons/04-accounting-data/export_issuers.py
Результат: data/issuers-source.parquet и data/issuers-source.json (версия RFSD).
ИНН – головная компания-эмитент (ПАО), сверены по названиям и раскрытию эмитентов.
"""
from pathlib import Path
import json
import sys

import polars as pl

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "rfsd"))
from rfsd import data  # noqa: E402

ISSUERS = {   # тикер: (ИНН эмитента, краткое название)
    "AFLT": ("7712040126", "ПАО «Аэрофлот»"), "ALRS": ("1433000147", "ПАО «АЛРОСА»"),
    "BSPB": ("7831000027", "ПАО «Банк «Санкт-Петербург»"), "CHMF": ("3528000597", "ПАО «Северсталь»"),
    "FEES": ("4716016979", "ПАО «Россети»"), "GAZP": ("7736050003", "ПАО «Газпром»"),
    "GMKN": ("8401005730", "ПАО «ГМК «Норильский никель»"), "HYDR": ("2460066195", "ПАО «РусГидро»"),
    "IRAO": ("2320109650", "ПАО «Интер РАО»"), "LKOH": ("7708004767", "ПАО «ЛУКОЙЛ»"),
    "MAGN": ("7414003633", "ПАО «ММК»"), "MOEX": ("7702077840", "ПАО «Московская биржа»"),
    "MTSS": ("7740000076", "ПАО «МТС»"), "NLMK": ("4823006703", "ПАО «НЛМК»"),
    "NVTK": ("6316031581", "ПАО «НОВАТЭК»"), "PHOR": ("7736216869", "ПАО «ФосАгро»"),
    "PIKK": ("7713011336", "ПАО «ПИК-СЗ»"), "PLZL": ("7703389295", "ПАО «Полюс»"),
    "ROSN": ("7706107510", "ПАО «НК «Роснефть»"), "RUAL": ("3906394938", "МКПАО «ОК РУСАЛ»"),
    "SBER": ("7707083893", "ПАО Сбербанк"), "SBERP": ("7707083893", "ПАО Сбербанк"),
    "SIBN": ("5504036333", "ПАО «Газпром нефть»"), "SNGS": ("8602060555", "ПАО «Сургутнефтегаз»"),
    "TATN": ("1644003838", "ПАО «Татнефть»"), "TRNFP": ("7706061801", "ПАО «Транснефть»"),
}
LINES = ["line_1100", "line_1150", "line_1200", "line_1250", "line_1300", "line_1400", "line_1410",
         "line_1500", "line_1510", "line_1600", "line_1700", "line_2110", "line_2120", "line_2200",
         "line_2310", "line_2320", "line_2330", "line_2300", "line_2400", "line_4100", "line_4500"]
FLAGS = ["okved", "filed", "imputed", "outlier", "financial", "simplified"]

inns = sorted({v[0] for v in ISSUERS.values()})
rep = (data.scan(range(2018, 2026)).filter(pl.col("inn").is_in(inns))
       .select(["inn", "year"] + FLAGS + LINES).collect())
keys = pl.DataFrame({"ticker": list(ISSUERS), "inn": [v[0] for v in ISSUERS.values()],
                     "issuer": [v[1] for v in ISSUERS.values()]})
years = pl.DataFrame({"year": list(range(2018, 2026))}, schema={"year": pl.Int32})
out = (keys.join(years, how="cross").join(rep, on=["inn", "year"], how="left")
       .with_columns(pl.col("year").cast(pl.Int32), pl.col("filed").fill_null(0).cast(pl.Int8))
       .sort("ticker", "year"))
out.write_parquet(HERE / "data" / "issuers-source.parquet")
(HERE / "data" / "issuers-source.json").write_text(json.dumps(
    {"source": "RFSD (irlspbru/RFSD), CC BY 4.0", **{k: data.version().get(k) for k in ["sha", "hf_last_modified"]}},
    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(out.group_by("ticker").agg(pl.col("filed").sum().alias("filed_years"),
                                 pl.col("okved").drop_nulls().last()).sort("ticker"))

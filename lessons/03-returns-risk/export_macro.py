"""Выгрузить макроданные для блока «Финансовые данные» занятия 3 из rustata. Только автор курса.

Запуск из корня книги (нужен токен RUSTATA_TOKEN в .env или в переменных окружения):
    python lessons/03-returns-risk/export_macro.py

Результат: data/cpi-source.parquet (ИПЦ, % к предыдущему месяцу, Россия),
data/usdrub-source.parquet (официальный курс доллара США Банка России), data/macro-source.json.
Токен в файлы не попадает. build_data_slides.py работает только с этими файлами.
"""
from pathlib import Path
import datetime as dt
import io
import json
import sys

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from qf import secrets  # noqa: E402

API = "https://rustata.ru/api/v1"
HEADERS = {"Authorization": f"Bearer {secrets.get('RUSTATA_TOKEN')}"}
START = "2014-12"

# ИПЦ: набор ЕМИСС 31074, код 1 «Все товары и услуги» (из /reference/codes), к предыдущему месяцу.
CPI = {"dataset": "fedstat/indicator_31074", "geo": "country", "class": "1", "measure": "MOM"}
resp = requests.get(f"{API}/data", headers=HEADERS, timeout=60,
                    params={**CPI, "start": START, "format": "csv"})
resp.raise_for_status()
cpi = pd.read_csv(io.StringIO(resp.text), sep=";", parse_dates=["period"])
assert cpi["geo"].nunique() == 1 and cpi["series_key"].nunique() == 1, "ожидался один ряд по России"
cpi = cpi[["period", "value"]].rename(columns={"value": "cpi_mom"}).sort_values("period")
cpi.to_parquet(HERE / "data" / "cpi-source.parquet", index=False)

# Курс доллара: ряд cbr/fx_daily, код USD (ключ из /series/search).
USD_KEY = "s1_qfc54254m35y2ayc"
items, start = [], "2014-12-01"
while True:
    resp = requests.get(f"{API}/series/{USD_KEY}/observations", headers=HEADERS, timeout=60,
                        params={"start": start, "limit": 5000})
    resp.raise_for_status()
    page = resp.json()["items"]
    items += page
    if len(page) < 5000:
        break
    start = str(pd.Timestamp(page[-1]["period"]) + pd.Timedelta(days=1))[:10]
usd = (pd.DataFrame(items)[["period", "value"]].rename(columns={"value": "usdrub"})
       .assign(period=lambda d: pd.to_datetime(d["period"])).drop_duplicates("period").sort_values("period"))
usd.to_parquet(HERE / "data" / "usdrub-source.parquet", index=False)

# Размер каталога для слайда о rustata.
resp = requests.get(f"{API}/reference/datasets", headers=HEADERS, timeout=60)
resp.raise_for_status()
catalog = resp.json()
catalog = catalog.get("items", catalog) if isinstance(catalog, dict) else catalog
providers = sorted({d["dataset"].split("/")[0] for d in catalog})

info = {"source": "rustata.ru API v1",
        "exported": str(dt.date.today()),
        "catalog": {"datasets": len(catalog), "providers": providers,
                    "series": int(sum(d.get("series_count", 0) for d in catalog))},
        "cpi": {**CPI, "first": str(cpi["period"].min().date()), "last": str(cpi["period"].max().date())},
        "usdrub": {"series_key": USD_KEY, "dataset": "cbr/fx_daily",
                   "first": str(usd["period"].min().date()), "last": str(usd["period"].max().date())}}
(HERE / "data" / "macro-source.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8")
print(json.dumps(info, ensure_ascii=False, indent=2))

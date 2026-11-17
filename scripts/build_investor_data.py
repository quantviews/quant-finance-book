"""Снимок для разделов о деньгах инвестора (глава 4) и типах ОФЗ (глава 13). Только автор книги.

    python scripts/build_investor_data.py

Нужен токен RUSTATA_TOKEN (.env) для ИПЦ; остальное – открытый ISS Московской биржи.
Результат в data/investor/:
  cpi.parquet      – ИПЦ России, в % к предыдущему месяцу (предыдущий месяц = 100) (Росстат, ЕМИСС 31074, через rustata);
  funds.parquet    – БПИФ на индекс Мосбиржи: дневные закрытия, режимы TQTF и TQBR склеены;
  ofz.parquet      – котировки четырёх ОФЗ разных типов (ПД, ПК, ИН);
  ofz_coupons.parquet – купоны этих выпусков (фактически выплаченные суммы);
  snapshot.json    – дата среза, источники, SHA256 файлов.
"""
from pathlib import Path
import datetime as dt
import hashlib
import io
import json
import sys

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qf import secrets  # noqa: E402

OUT = ROOT / "data" / "investor"
END = "2026-09-30"                     # та же дата среза, что у снимка облигаций
ISS = "https://iss.moex.com/iss"
RUSTATA = "https://rustata.ru/api/v1"
FUNDS = ["TMOS", "SBMX", "EQMX"]
OFZ = {"SU26238RMFS4": "ПД", "SU26235RMFS0": "ПД", "SU29013RMFS8": "ПК", "SU52003RMFS9": "ИН"}
OFZ_START = "2023-01-01"


def iss_history(path: str, params: dict) -> pd.DataFrame:
    rows, start = [], 0
    while True:
        j = requests.get(f"{ISS}/history/{path}.json", timeout=60,
                         params={**params, "start": start, "iss.meta": "off"}).json()["history"]
        if not j["data"]:
            return pd.DataFrame(rows, columns=j["columns"])
        rows += j["data"]
        start += len(j["data"])


# ИПЦ
resp = requests.get(f"{RUSTATA}/data", timeout=60,
                    headers={"Authorization": f"Bearer {secrets.get('RUSTATA_TOKEN')}"},
                    params={"dataset": "fedstat/indicator_31074", "geo": "country", "class": "1",
                            "measure": "MOM", "start": "2002-12", "end": END[:7], "format": "csv"})
resp.raise_for_status()
cpi = pd.read_csv(io.StringIO(resp.text), sep=";", parse_dates=["period"])
assert cpi["series_key"].nunique() == 1, "ожидался один ряд по России"
cpi = (cpi[["period", "value"]].rename(columns={"period": "date", "value": "cpi_mom"})
       .sort_values("date").reset_index(drop=True))
assert cpi["date"].diff().dt.days.dropna().between(28, 31).all(), "пропуск месяца в ИПЦ"
assert cpi["cpi_mom"].between(95, 110).all(), "ИПЦ должен быть в % к предыдущему месяцу (около 100)"

# Фонды: до 19.06.2026 – режим TQTF, с 22.06.2026 – TQBR.
funds = []
for t in FUNDS:
    h = iss_history(f"engines/stock/markets/shares/securities/{t}", {"till": END})
    h = h[h["BOARDID"].isin(["TQTF", "TQBR"]) & h["CLOSE"].notna()]
    assert not h.duplicated("TRADEDATE").any(), f"{t}: одна дата в двух режимах"
    funds.append(h.assign(ticker=t)[["TRADEDATE", "ticker", "BOARDID", "CLOSE", "VOLUME", "VALUE"]])
funds = (pd.concat(funds).rename(columns={"TRADEDATE": "date", "BOARDID": "board", "CLOSE": "close_raw",
                                          "VOLUME": "volume", "VALUE": "value_rub"})
         .assign(date=lambda d: pd.to_datetime(d["date"])).sort_values(["ticker", "date"]).reset_index(drop=True))
# Сплиты паёв (SBMX 1:100 в июне 2021 г.): цены до сплита – в текущей базе.
j = requests.get(f"{ISS}/statistics/engines/stock/splits.json", params={"iss.meta": "off"}, timeout=60).json()["splits"]
splits = pd.DataFrame(j["data"], columns=j["columns"])
splits = splits[splits["secid"].isin(FUNDS)]
funds["close"] = funds["close_raw"].astype(float)
for s in splits.itertuples():
    before = (funds["ticker"] == s.secid) & (funds["date"] <= pd.Timestamp(s.tradedate))
    funds.loc[before, "close"] *= s.before / s.after
    funds.loc[before, "volume"] *= s.after / s.before
jumps = funds.groupby("ticker")["close"].pct_change().abs()
assert (jumps.dropna() < 0.25).all(), f"скачок цены фонда – проверить сплит:\n{funds[jumps >= 0.25]}"

# ОФЗ
quotes, coupons = [], []
for secid, kind in OFZ.items():
    h = iss_history(f"engines/stock/markets/bonds/boards/TQOB/securities/{secid}",
                    {"from": OFZ_START, "till": END})
    h = h[h["CLOSE"].notna()]
    quotes.append(pd.DataFrame({
        "date": pd.to_datetime(h["TRADEDATE"]), "secid": secid, "name": h["SHORTNAME"], "type": kind,
        "clean_pct": h["CLOSE"], "accrued": h["ACCINT"], "face_value": h["FACEVALUE"],
        "ytm_pct": pd.to_numeric(h["YIELDCLOSE"]), "bei_pct": pd.to_numeric(h["BEICLOSE"]),
        "duration_days": pd.to_numeric(h["DURATION"]), "value_rub": h["VALUE"],
        "maturity": pd.to_datetime(h["MATDATE"])}))
    j = requests.get(f"{ISS}/securities/{secid}/bondization.json", timeout=60,
                     params={"iss.meta": "off", "limit": 200}).json()["coupons"]
    c = pd.DataFrame(j["data"], columns=j["columns"])
    c = c[(c["coupondate"] >= OFZ_START) & (c["coupondate"] <= END)]
    assert c["value_rub"].notna().all(), f"{secid}: неизвестный купон до даты среза"
    coupons.append(pd.DataFrame({"secid": secid, "payment_date": pd.to_datetime(c["coupondate"]),
                                 "period_start": pd.to_datetime(c["startdate"]),
                                 "amount": c["value_rub"], "rate_pct": c["valueprc"]}))
quotes = pd.concat(quotes).sort_values(["secid", "date"]).reset_index(drop=True)
coupons = pd.concat(coupons).sort_values(["secid", "payment_date"]).reset_index(drop=True)

OUT.mkdir(parents=True, exist_ok=True)
files = {"cpi.parquet": cpi, "funds.parquet": funds, "ofz.parquet": quotes, "ofz_coupons.parquet": coupons}
meta = {"end": END, "built": str(dt.date.today()),
        "sources": {"cpi": "Росстат, ЕМИСС 31074 (все товары и услуги, к предыдущему месяцу), через rustata.ru API v1",
                    "funds": "MOEX ISS, режимы TQTF (до 19.06.2026) и TQBR (с 22.06.2026)",
                    "ofz": "MOEX ISS, режим TQOB; купоны – bondization"},
        "funds": FUNDS, "fund_splits": splits[["tradedate", "secid", "before", "after"]].to_dict("records"),
        "ofz": OFZ, "files": {}}
for name, df in files.items():
    df.to_parquet(OUT / name, index=False)
    meta["files"][name] = {"rows": len(df), "sha256": hashlib.sha256((OUT / name).read_bytes()).hexdigest()}
(OUT / "snapshot.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: v["rows"] for k, v in meta["files"].items()}, ensure_ascii=False),
      "ИПЦ:", cpi["date"].min().date(), "–", cpi["date"].max().date())
print(funds.groupby("ticker")["date"].agg(["min", "max", "count"]).to_string())

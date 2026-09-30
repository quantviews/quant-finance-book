"""Выручка организаций по классам ОКВЭД по данным Росстата (через API rustata).

    python scripts/build_rosstat.py

Набор showdata/indicator_278140 «Выручка организаций»: годовые значения в тыс. руб.
(ОКЕИ 384) – в тех же единицах, что и RFSD. Берём Россию, все организации (measure=TOTAL),
головной ряд «Всего по обследуемым видам экономической деятельности» и двузначные классы.
Токен RUSTATA_TOKEN – из переменной окружения или .env (qf.secrets).
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pandas as pd
import requests

BOOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BOOK))
from qf import secrets  # noqa: E402

API = "https://rustata.ru/api/v1"
DATASET = "showdata/indicator_278140"
HEAD = "101.АГ"                         # «Всего по обследуемым видам экономической деятельности»


def get(path: str, **params) -> requests.Response:
    r = requests.get(f"{API}{path}", params=params, timeout=120,
                     headers={"Authorization": f"Bearer {secrets.get('RUSTATA_TOKEN')}"})
    r.raise_for_status()
    return r


def main() -> None:
    codes = get("/reference/codes", dataset=DATASET).json()["items"]
    classes = [c["class"] for c in codes if re.fullmatch(r"\d{2}", c["class"])]
    names = {c["class"]: c["name"] for c in codes}
    frames = []
    for chunk in [[HEAD] + classes[:40], classes[40:]]:
        body = get("/data", dataset=DATASET, geo="643", measure="TOTAL", start="2017",
                   format="csv", limit=200, **{"class": ",".join(chunk)}).text
        frames.append(pd.read_csv(io.StringIO(body), sep=";", dtype={"class": str}))
    df = pd.concat(frames)
    out = (df.assign(year=pd.to_datetime(df["period"]).dt.year,
                     okved=df["class"],
                     name=df["class"].map(names),
                     revenue=df["value"])                    # тыс. руб.
             [["okved", "name", "year", "revenue"]]
             .drop_duplicates(["okved", "year"], keep="last")
             .sort_values(["okved", "year"]))
    out.to_parquet(BOOK / "data" / "rosstat_revenue.parquet", index=False)
    print(f"{out['okved'].nunique()} классов, {out['year'].min()}–{out['year'].max()}, {len(out)} строк")


if __name__ == "__main__":
    main()

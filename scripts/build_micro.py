"""Данные к главе 17 «Микроструктура рынка».

    python scripts/build_micro.py [--rl-data F:/data/rl]

Два источника из проекта RL (журнал заявок Московской биржи):

1. Репликационный пакет статьи «Больше розницы, не меньше эффективности»
   (`<rl-data>/replication/data`, лицензия CC BY 4.0): панель тикер-дней
   2021–2025 и сопутствующие таблицы. Это производные показатели, не данные биржи.

2. Один торговый день SBER (30.12.2025), основная сессия 10:00–18:40, в агрегированном
   виде: снимки пяти лучших уровней стакана на секундной сетке и лента сделок
   со знаком агрессора. Сырой журнал заявок и снимки на сетке 100 мс не публикуются.

Результат – папка data/micro/.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

BOOK = Path(__file__).resolve().parents[1]
OUT = BOOK / "data" / "micro"
DAY = "2025-12-30"
T0, T1 = 10 * 3600, 18 * 3600 + 40 * 60          # основная сессия, секунды от полуночи (МСК)
LEVELS = 5


def build_panel(rep: Path) -> None:
    d = rep / "data"
    uni = pd.read_csv(d / "universe.csv")
    panel = pd.read_csv(d / "panel_5s.csv", parse_dates=["date"])
    panel = panel.merge(uni[["ticker", "tier", "sector"]], on="ticker", how="left")
    panel.to_parquet(OUT / "panel_5s.parquet", index=False)
    pd.read_csv(d / "price_variable.csv", parse_dates=["date"]).to_parquet(
        OUT / "price_variable.parquet", index=False)
    pd.read_csv(d / "net_edge_q15.csv", parse_dates=["date"]).to_parquet(
        OUT / "net_edge.parquet", index=False)
    uni.to_csv(OUT / "universe.csv", index=False)
    shutil.copy(d / "ofi_horizon.csv", OUT / "ofi_horizon.csv")
    regimes = pd.read_excel(d / "figure_data.xlsx", sheet_name="fig6_regimes")
    regimes.to_csv(OUT / "vr_monthly.csv", index=False)
    shutil.copy(rep / "LICENSE-data", OUT / "LICENSE-data")


def build_book(rl: Path) -> None:
    snap = pd.read_parquet(rl / "snapshots" / f"date={DAY}" / "sec=SBER" / "snapshots.parquet")
    s = snap["ts_us"].to_numpy()
    keep = (s % 1_000_000 == 0) & (s > T0 * 1_000_000) & (s <= T1 * 1_000_000)
    snap = snap.loc[keep].reset_index(drop=True)
    out = {"time": pd.Timestamp(DAY) + pd.to_timedelta(snap["ts_us"], unit="us")}
    for side in ("bid", "ask"):
        px = np.full((len(snap), LEVELS), np.nan)
        qty = np.zeros((len(snap), LEVELS), dtype=np.int64)
        for i, (p, q) in enumerate(zip(snap[f"{side}_px_e6"], snap[f"{side}_qty"])):
            k = min(LEVELS, len(p))
            px[i, :k] = np.asarray(p[:k]) / 1e6
            qty[i, :k] = q[:k]
        for j in range(LEVELS):
            out[f"{side}_px{j + 1}"] = px[:, j]
            out[f"{side}_qty{j + 1}"] = qty[:, j]
    book = pd.DataFrame(out)
    cols = ["time"] + [f"{s_}_{f}{j}" for j in range(1, LEVELS + 1)
                       for s_ in ("bid", "ask") for f in ("px", "qty")]
    book[cols].to_parquet(OUT / "sber_book.parquet", index=False)


def build_trades(rl: Path) -> None:
    log = pd.read_parquet(rl / "parquet" / "orderlog" / f"date={DAY}" / "sec=SBER" / "part.parquet")
    t = log[(log["action"] == 2)
            & (log["ts_us"] >= T0 * 1_000_000) & (log["ts_us"] < T1 * 1_000_000)].copy()
    t = t.sort_values(["trade_no", "order_no"])
    # агрессор – заявка с большим номером: пассивная стояла в книге раньше
    agg = t.groupby("trade_no", sort=False).tail(1)
    trades = pd.DataFrame({
        "time": pd.Timestamp(DAY) + pd.to_timedelta(agg["ts_us"].to_numpy(), unit="us"),
        "price": agg["trade_price_e6"].to_numpy() / 1e6,
        "qty": agg["volume"].to_numpy(),
        "side": agg["side"].to_numpy().astype("int8"),
    }).sort_values("time", kind="stable").reset_index(drop=True)
    trades.to_parquet(OUT / "sber_trades.parquet", index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rl-data", default="F:/data/rl", type=Path)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    build_panel(a.rl_data / "replication")
    build_book(a.rl_data)
    build_trades(a.rl_data)
    for f in sorted(OUT.iterdir()):
        print(f"{f.name:28s} {f.stat().st_size / 1e6:6.2f} МБ")


if __name__ == "__main__":
    main()

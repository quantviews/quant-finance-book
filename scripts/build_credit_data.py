"""Данные к главе 14 «Кредитный риск»: только агрегаты.

    python scripts/build_credit_data.py

Источники (нужны только автору):
- календарь дефолтов Cbonds 2022–2026 (`F:/Yandex.Disk/FINANCE/cbonds/cbonds-defaults_*.xlsx`);
  лицензионные данные, в книгу не попадают ни строки, ни списки выпусков и эмитентов;
- история торгов, карточки выпусков и параметры КБД Московской биржи (moexutils DuckLake).

Результат – папка data/credit/: таблицы, в которых каждая строка объединяет
несколько эмитентов (агрегаты по годам, корзинам спреда и дням относительно события),
и биржевой срез корпоративных облигаций на одну дату без меток дефолта.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BOOK = Path(__file__).resolve().parents[1]
OUT = BOOK / "data" / "credit"
CBONDS = Path("F:/Yandex.Disk/FINANCE/cbonds")
CBONDS_FILES = ["cbonds-defaults_2022-2024.xlsx", "cbonds-defaults_2025-2026.xlsx"]
PANEL_START = "2020-07-01"           # запас истории для окон до первых событий 2022 г.
DATA_END = pd.Timestamp("2026-10-02")  # последняя дата выгрузки Cbonds
XS_DATE = pd.Timestamp("2026-09-29")   # срез для практикума: последняя дата КБД в основном снимке
MIN_GROUP = 3                          # меньше трёх эмитентов в ячейке – значение не публикуется

FIXED = {
    "Облигация с фиксированным (известным) купоном", "Фикс с известным купоном",
    "Амортизируемая облигация", "Амортизируемые облигации", "Дисконтная облигация",
}
DEFAULT_STATUS = {"Дефолт", "Неисполнение оферты"}
PAY_EVENTS = {"Дефолт: купон", "Дефолт: погашение", "Дефолт: оферта"}


# ---------------------------------------------------------------- КБД
def zero_yield_pct(years, pars):
    """Эффективная годовая ставка КБД (%) по параметрам MOEX: Нельсон – Сигель
    в б. п. непрерывного начисления плюс девять гауссовых поправок."""
    t = np.asarray(years, dtype=float)
    p = {k: np.asarray(pars[k], dtype=float) for k in ["B1", "B2", "B3", "T1"] + [f"G{i}" for i in range(1, 10)]}
    x = t / p["T1"]
    f = -np.expm1(-x) / x
    g = p["B1"] + p["B2"] * f + p["B3"] * (f - np.exp(-x))
    centers = [0.0, 0.6]
    for i in range(2, 9):
        centers.append(centers[-1] + 0.6 * 1.6 ** (i - 1))
    for i, a in enumerate(centers):
        g = g + p[f"G{i + 1}"] * np.exp(-(((t - a) / (0.6 * 1.6 ** i)) ** 2))
    return 100 * np.expm1(g / 10000)


# ---------------------------------------------------------------- исходные данные
def load_defaults(sec: pd.DataFrame) -> pd.DataFrame:
    d = pd.concat([pd.read_excel(CBONDS / f) for f in CBONDS_FILES], ignore_index=True)
    d = d.rename(columns={
        "Дата": "date", "Тип события": "event", "Бумага": "paper", "ISIN": "isin",
        "Валюта": "currency", "Статус дефолта": "status", "Причина дефолта": "reason",
        "Объем неисполненных обязательств": "unpaid",
        "Плановая дата исполнения обязательств": "planned",
    })
    d["date"] = pd.to_datetime(d["date"])
    d["planned"] = pd.to_datetime(d["planned"])
    # Дата события – первая из даты записи и плановой даты платежа.
    d["ev"] = d[["date", "planned"]].min(axis=1)
    ids = sec.dropna(subset=["ISIN"]).drop_duplicates("ISIN").set_index("ISIN")["EMITTER_ID"]
    d["emitter"] = d["isin"].map(ids)
    # Выпуски вне биржи (КО, еврооблигации): ключ – название эмитента до запятой.
    d["issuer"] = np.where(d["emitter"].notna(), "moex:" + d["emitter"].astype("Int64").astype(str),
                           "name:" + d["paper"].str.split(",").str[0].str.strip())
    d["on_moex"] = d["emitter"].notna()
    return d


def load_moex():
    from moexutils import lake
    snap = int(lake.snapshots()["snapshot_id"].max())
    sec = lake.query(
        "SELECT SECID, ISIN, EMITTER_ID, TYPE, BOND_TYPE, COUPON_BENCHMARK, FACEUNIT, "
        "INITIALFACEVALUE, ISSUESIZE, ISSUEDATE, MATDATE, LISTLEVEL "
        f"FROM {lake.ref('bonds_securities', snap)} WHERE TYPE IN ('corporate_bond', 'exchange_bond')"
    ).to_pandas()
    panel = lake.query(
        "SELECT date, SECID, BOARDID, SHORTNAME, WAPRICE, YIELDATWAP, DURATION, VALUE, FACEUNIT, BONDTYPE "
        f"FROM {lake.ref('bonds', snap)} "
        "WHERE BOARDID IN ('TQCB', 'TQIR') AND date >= ? AND date <= ? AND VOLUME > 0 AND WAPRICE > 0 "
        "AND FACEUNIT IN ('RUB', 'SUR', 'RUR')",
        [pd.Timestamp(PANEL_START).date(), DATA_END.date()],
    ).to_pandas()
    # TQCB – основной режим, TQIR – сектор повышенного инвестиционного риска.
    # Если выпуск в один день торговался в обоих, берём режим с большим оборотом.
    panel = (panel.sort_values(["date", "SECID", "VALUE"], ascending=[True, True, False])
             .drop_duplicates(["date", "SECID"]).reset_index(drop=True))
    # TQRD – режим торгов облигациями в дефолте: первая сделка там означает, что дефолт уже был.
    rd = lake.query(
        f"SELECT SECID, min(date) AS rd_first FROM {lake.ref('bonds', snap)} "
        "WHERE BOARDID = 'TQRD' AND VOLUME > 0 GROUP BY SECID"
    ).to_pandas()
    params = lake.query(f"SELECT * FROM {lake.ref('zcyc_params', snap)}").to_pandas()
    nodes = lake.query(f"SELECT * FROM {lake.ref('zcyc_yields', snap)}").to_pandas()
    return snap, sec, panel, params, nodes, rd


def coupon_kind(sec: pd.DataFrame, panel: pd.DataFrame) -> pd.Series:
    """fixed / unknown / other по карточке и последнему известному типу в истории торгов."""
    last_hist = panel.dropna(subset=["BONDTYPE"]).sort_values("date").groupby("SECID")["BONDTYPE"].last()
    s = sec.set_index("SECID")
    kind = s["BOND_TYPE"].combine_first(last_hist.reindex(s.index))
    out = pd.Series("unknown", index=s.index)
    out[kind.isin(FIXED)] = "fixed"
    out[kind.notna() & ~kind.isin(FIXED)] = "other"
    out[s["COUPON_BENCHMARK"].notna()] = "other"          # флоатер
    return out


def add_gspread(panel: pd.DataFrame, params: pd.DataFrame, nodes: pd.DataFrame) -> pd.DataFrame:
    keys = [c for c in params.columns if c not in ("date", "tradetime")]
    chk = nodes.merge(params, on="date", validate="m:1")
    err = np.abs(zero_yield_pct(chk["period"], {k: chk[k] for k in keys}) - chk["value"])
    assert err.max() < 0.00011, f"КБД не совпадает с опубликованными узлами: {err.max()}"
    p = panel.merge(params[["date"] + keys], on="date", how="left")
    ok = p["B1"].notna() & (p["DURATION"] > 0) & p["YIELDATWAP"].notna() & (p["YIELDATWAP"] != 0) & (p["YIELDATWAP"] > -100)
    g = np.full(len(p), np.nan)
    sub = p.loc[ok]
    g[ok.to_numpy()] = 100 * (sub["YIELDATWAP"] - zero_yield_pct(sub["DURATION"] / 365, {k: sub[k] for k in keys}))
    panel = panel.copy()
    panel["g_bp"] = g
    return panel


# ---------------------------------------------------------------- агрегаты
def issuer_first_default(d: pd.DataFrame) -> pd.DataFrame:
    pay = d[d["event"].isin(PAY_EVENTS)]
    real = pay[pay["status"].isin(DEFAULT_STATUS)].groupby("issuer")["ev"].min().rename("default_ev")
    # Первое платёжное событие любого статуса: технический дефолт может предшествовать настоящему.
    first_any = pay.groupby("issuer")["ev"].min().rename("first_ev")
    out = pd.concat([first_any, real], axis=1)
    out["defaulted"] = out["default_ev"].notna()
    # Дата дефолта эмитента – первое платёжное событие, если позже последовал настоящий дефолт.
    out["d_date"] = out["first_ev"].where(out["defaulted"])
    out["on_moex"] = d.groupby("issuer")["on_moex"].first()
    return out


def table_events(d: pd.DataFrame, iss: pd.DataFrame) -> pd.DataFrame:
    d = d.assign(year=d["date"].dt.year)
    status = d["status"].map({
        "Дефолт": "дефолт", "Неисполнение оферты": "дефолт",
        "Технический дефолт": "технический, не исполнено",
        "Технический дефолт (обязательство исполнено)": "технический, исполнено",
    })
    event = d["event"].str.replace("Дефолт: ", "", regex=False).str.replace("Реструктуризация", "реструктуризация")
    t = (d.assign(status=status, event=event)
         .groupby(["year", "event", "status"])
         .agg(rows=("isin", "size"), issues=("isin", "nunique"), issuers=("issuer", "nunique"),
              unpaid_mln=("unpaid", lambda x: x.sum() / 1e6))
         .reset_index())
    # Сколько эмитентов впервые попали в календарь и сколько из них – настоящий дефолт.
    first = iss.assign(year=iss["first_ev"].dt.year)
    new = first.groupby("year").agg(new_issuers=("first_ev", "size"),
                                    new_defaulters=("defaulted", "sum"),
                                    new_on_moex=("on_moex", "sum"))
    tot = d.groupby("year").agg(rows=("isin", "size"), issues=("isin", "nunique"),
                                issuers=("issuer", "nunique"), unpaid_mln=("unpaid", lambda x: x.sum() / 1e6))
    by_year = tot.join(new, how="outer").fillna(0).reset_index()
    by_year = by_year[by_year["year"] >= 2022]   # 2021 – только плановые даты событий начала 2022 г.
    reasons = (d.drop_duplicates(["issuer", "reason"])
               .groupby("reason")["issuer"].nunique().rename("issuers").reset_index())
    return t, by_year, reasons


def issuer_outstanding(sec: pd.DataFrame, date: pd.Timestamp) -> pd.Series:
    s = sec[sec["FACEUNIT"].isin(["RUB", "SUR", "RUR"])].copy()
    s["ISSUEDATE"] = pd.to_datetime(s["ISSUEDATE"], errors="coerce")
    s["MATDATE"] = pd.to_datetime(s["MATDATE"], errors="coerce")
    live = (s["ISSUEDATE"] <= date) & ((s["MATDATE"] > date) | s["MATDATE"].isna())
    vol = (s["INITIALFACEVALUE"] * s["ISSUESIZE"]).where(live)
    return vol.groupby("moex:" + s["EMITTER_ID"].astype("Int64").astype(str)).sum()


SIZE_BINS = [0, 2e9, 10e9, np.inf]
SIZE_LABELS = ["до 2 млрд руб.", "2–10 млрд руб.", "более 10 млрд руб."]


def table_rates(panel: pd.DataFrame, sec: pd.DataFrame, iss: pd.DataFrame, rd_first: pd.Series) -> pd.DataFrame:
    """Когорты: эмитенты с торгами в IV квартале предыдущего года, ещё без дефолта."""
    rows = []
    for year in range(2022, 2027):
        start = pd.Timestamp(year, 1, 1)
        end = min(pd.Timestamp(year, 12, 31), DATA_END)
        q4 = panel[(panel["date"] >= start - pd.Timedelta(days=92)) & (panel["date"] < start)]
        cohort = pd.Index(q4["issuer"].dropna().unique())
        prior = iss.loc[iss.index.intersection(cohort), "d_date"]
        in_rd = rd_first[rd_first < start].index                       # уже торгуются как дефолтные
        cohort = cohort[~cohort.isin(prior[prior < start].index) & ~cohort.isin(in_rd)]
        dd = iss["d_date"].reindex(cohort)
        hit = (dd >= start) & (dd <= end)
        size = pd.cut(issuer_outstanding(sec, start).reindex(cohort).fillna(0), SIZE_BINS,
                      labels=SIZE_LABELS, right=False)
        df = pd.DataFrame({"size": size, "hit": hit.to_numpy()})
        for lab, g in [("все", df)] + [(s, df[df["size"] == s]) for s in SIZE_LABELS]:
            rows.append({"year": year, "months": end.month if year == DATA_END.year else 12,
                         "size": lab, "issuers": len(g), "defaults": int(g["hit"].sum())})
    return pd.DataFrame(rows)


SPREAD_BINS = [-np.inf, 100, 200, 400, 700, 1000, np.inf]
SPREAD_LABELS = ["до 100", "100–200", "200–400", "400–700", "700–1000", "более 1000"]


def issuer_month_spreads(panel: pd.DataFrame) -> pd.DataFrame:
    """Медианный G-спред эмитента на конец месяца по последним наблюдениям за 10 дней."""
    ok = panel[(panel["kind"] != "other") & panel["g_bp"].notna() & (panel["DURATION"] >= 90)]
    ends = pd.date_range("2021-12-31", "2026-09-30", freq="ME")
    out = []
    for t in ends:
        w = ok[(ok["date"] > t - pd.Timedelta(days=10)) & (ok["date"] <= t)]
        last = w.sort_values("date").groupby("SECID").tail(1)
        g = last.groupby("issuer").agg(g_bp=("g_bp", "median"), fixed=("kind", lambda k: (k == "fixed").all()))
        g["t"] = t
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True)


def table_spreads(ims: pd.DataFrame, iss: pd.DataFrame):
    dd = iss["d_date"].reindex(ims["issuer"]).to_numpy()
    ims = ims.assign(d_date=dd)
    ims = ims[~(ims["d_date"] <= ims["t"])].copy()               # уже в дефолте – не в выборке
    ims["hit"] = (ims["d_date"] > ims["t"]) & (ims["d_date"] <= ims["t"] + pd.Timedelta(days=365))
    # Медианы и квантили спреда по месяцам – картина рынка без меток дефолта.
    market = ims.groupby("t")["g_bp"].quantile([0.25, 0.5, 0.75, 0.9]).unstack().reset_index()
    market.columns = ["t", "q25", "q50", "q75", "q90"]
    market["issuers"] = ims.groupby("t")["issuer"].nunique().to_numpy()
    # Для калибровки нужен полный горизонт 12 месяцев до конца выгрузки дефолтов.
    ims = ims[ims["t"] + pd.Timedelta(days=365) <= DATA_END].copy()
    ims["bucket"] = pd.cut(ims["g_bp"], SPREAD_BINS, labels=SPREAD_LABELS, right=False)
    ims["year"] = ims["t"].dt.year
    def agg(g):
        return pd.Series({"obs": len(g), "issuers": g["issuer"].nunique(), "defaults": int(g["hit"].sum()),
                          "default_issuers": g.loc[g["hit"], "issuer"].nunique(),
                          "g_median": g["g_bp"].median()})
    total = ims.groupby("bucket", observed=True).apply(agg, include_groups=False).reset_index()
    total["sample"] = "all"
    fixed = ims[ims["fixed"]].groupby("bucket", observed=True).apply(agg, include_groups=False).reset_index()
    fixed["sample"] = "fixed"
    by_year = ims.groupby(["year", "bucket"], observed=True).apply(agg, include_groups=False).reset_index()
    return pd.concat([total, fixed], ignore_index=True), by_year, market


RATING_INDEXES = {"RUCBCPAAANS": "AAA", "RUCBCPAANS": "AA", "RUCBCPANS": "A", "RUCBCPBBBNS": "BBB"}


def table_rating_spreads(snap: int, params: pd.DataFrame) -> pd.DataFrame:
    """G-спред индексов корпоративных облигаций Мосбиржи по рейтинговым группам, медиана за месяц.

    Доходность индекса – эффективная годовая, дюрация – в днях; спред считается к КБД
    на дюрации индекса, как для отдельного выпуска."""
    from moexutils import lake
    tickers = ", ".join(f"'{t}'" for t in RATING_INDEXES)
    idx = lake.query(
        f"SELECT date, SECID AS ticker, YIELD, DURATION FROM {lake.ref('indexes_all', snap)} "
        f"WHERE SECID IN ({tickers}) AND date >= ? AND date <= ? AND YIELD > 0 AND DURATION > 0",
        [pd.Timestamp("2021-12-01").date(), DATA_END.date()],
    ).to_pandas()
    idx["date"] = pd.to_datetime(idx["date"])
    keys = [c for c in params.columns if c not in ("date", "tradetime")]
    pr = params.assign(date=pd.to_datetime(params["date"]))[["date"] + keys]
    idx = idx.merge(pr, on="date", how="inner")
    idx["g_bp"] = 100 * (idx["YIELD"] - zero_yield_pct(idx["DURATION"] / 365, {k: idx[k] for k in keys}))
    idx["t"] = idx["date"] + pd.offsets.MonthEnd(0)
    # Медиана дневных значений за месяц: пока выпуск с обвалившейся ценой не исключён из индекса,
    # доходность индекса может на несколько дней уходить в сотни процентов.
    m = (idx.groupby(["ticker", "t"])
         .agg(yield_pct=("YIELD", "median"), duration_days=("DURATION", "median"),
              g_bp=("g_bp", "median"), yield_max=("YIELD", "max"))
         .reset_index())
    out = pd.DataFrame({
        "t": m["t"], "index": m["ticker"], "rating": m["ticker"].map(RATING_INDEXES),
        "yield_pct": m["yield_pct"], "duration_days": m["duration_days"], "g_bp": m["g_bp"],
        "yield_max": m["yield_max"],
    })
    out = out[out["t"] <= pd.Timestamp("2026-09-30")]
    out["rating"] = pd.Categorical(out["rating"], categories=list(RATING_INDEXES.values()), ordered=True)
    return out.sort_values(["rating", "t"]).reset_index(drop=True)


def trading_index(panel: pd.DataFrame) -> pd.Series:
    days = pd.Index(np.sort(panel["date"].unique()))
    return pd.Series(np.arange(len(days)), index=days)


def table_event_paths(panel: pd.DataFrame, iss: pd.DataFrame, K0=-250, K1=60) -> pd.DataFrame:
    idx = trading_index(panel)
    days = idx.index
    dflt = iss[iss["defaulted"] & iss["on_moex"] & (iss["d_date"] >= pd.Timestamp("2022-03-01"))]
    rows = []
    for issuer, ev in dflt["d_date"].items():
        p = panel[panel["issuer"] == issuer]
        if p.empty:
            continue
        k0 = idx.iloc[days.searchsorted(ev)] if ev <= days[-1] else None
        if k0 is None:
            continue
        p = p.assign(k=idx.reindex(p["date"]).to_numpy() - k0,
                     g_bp=p["g_bp"].where(p["kind"] != "other"))
        p = p[(p["k"] >= K0) & (p["k"] <= K1)]
        if p.empty:
            continue
        base = p.loc[(p["k"] >= K0) & (p["k"] <= -121)].groupby("date")["VALUE"].sum().median()
        daily = p.groupby("k").agg(price=("WAPRICE", "median"),
                                   g_bp=("g_bp", "median"),
                                   value=("VALUE", "sum"))
        daily["turnover_ratio"] = daily["value"] / base if base and base > 0 else np.nan
        daily["issuer"] = issuer
        rows.append(daily.reset_index())
    e = pd.concat(rows, ignore_index=True)
    q = lambda s, a: s.quantile(a)
    out = e.groupby("k").agg(
        issuers=("issuer", "nunique"),
        price_q25=("price", lambda s: q(s, .25)), price_q50=("price", "median"), price_q75=("price", lambda s: q(s, .75)),
        g_issuers=("g_bp", "count"), g_q50=("g_bp", "median"),
        g_q25=("g_bp", lambda s: q(s, .25)), g_q75=("g_bp", lambda s: q(s, .75)),
        turnover_q50=("turnover_ratio", "median"),
    ).reset_index()
    n_def = len(dflt)
    n_paths = e["issuer"].nunique()
    return out, {"issuers_defaulted_on_moex": int(n_def), "issuers_with_paths": int(n_paths)}


# ---------------------------------------------------------------- ранние сигналы
def price_signals(panel: pd.DataFrame, drop=0.10, excess=0.05, L=60) -> pd.DataFrame:
    """Сигнал по выпуску: чистая цена WAP за L наблюдений упала не меньше чем на `drop`
    и отстала от медианы рынка той же дюрационной группы на `excess`;
    условие выполнено три наблюдения подряд (разрыв не больше 7 дней)."""
    p = panel.sort_values(["SECID", "date"]).copy()
    g = p.groupby("SECID")
    p["p_lag"] = g["WAPRICE"].shift(L)
    p["d_lag"] = g["date"].shift(L)
    p["ret"] = p["WAPRICE"] / p["p_lag"] - 1
    p.loc[(p["date"] - p["d_lag"]).dt.days > 2 * L, "ret"] = np.nan
    p["dur_b"] = pd.cut(p["DURATION"] / 365, [-np.inf, 1, 3, np.inf], labels=False)
    p["mkt"] = p.groupby(["date", "dur_b"])["ret"].transform("median")
    p["cond"] = (p["ret"] <= -drop) & (p["ret"] - p["mkt"] <= -excess)
    gap_ok = (p["date"] - g["date"].shift(1)).dt.days <= 7
    c = p["cond"] & g["cond"].shift(1, fill_value=False) & g["cond"].shift(2, fill_value=False) \
        & gap_ok & gap_ok.groupby(p["SECID"]).shift(1, fill_value=False)
    return p.loc[c, ["date", "SECID", "issuer"]]


def cooldown(sig: pd.DataFrame, key: str, days=126) -> pd.DataFrame:
    keep = []
    for k, g in sig.sort_values("date").groupby(key):
        last = None
        for i, d in zip(g.index, g["date"]):
            if last is None or (d - last).days > days:
                keep.append(i)
                last = d
    return sig.loc[keep]


def evaluate(sig, iss, start, end, H=180, key="issuer", drop_post=True, incomplete="exclude", only_defaulted=False):
    s = sig[(sig["date"] >= start) & (sig["date"] <= end)].copy()
    s["d_date"] = iss["d_date"].reindex(s["issuer"]).to_numpy()
    if only_defaulted:
        s = s[s["d_date"].notna()]
    post = s["d_date"].notna() & (s["d_date"] <= s["date"])
    if drop_post:
        s = s[~post]
    s = cooldown(s, key)
    s["hit"] = (s["d_date"] > s["date"]) & (s["d_date"] <= s["date"] + pd.Timedelta(days=H))
    if not drop_post:
        s["hit"] |= s["d_date"].notna() & (s["d_date"] <= s["date"])
    complete = s["date"] + pd.Timedelta(days=H) <= DATA_END
    if incomplete == "exclude":
        s = s[complete | s["hit"]]
    return {"signals": len(s), "hits": int(s["hit"].sum()),
            "issuers": s["issuer"].nunique(), "hit_issuers": s.loc[s["hit"], "issuer"].nunique()}


def recall(sig, iss, panel, start, end, H=180):
    dflt = iss[iss["defaulted"] & iss["on_moex"] & (iss["d_date"] >= start) & (iss["d_date"] <= end)]
    traded = panel.groupby("issuer")["date"].agg(list)
    n = det = 0
    leads = []
    for issuer, ev in dflt["d_date"].items():
        dates = pd.Series(traded.get(issuer, []))
        if not ((dates >= ev - pd.Timedelta(days=H)) & (dates < ev)).any():
            continue
        n += 1
        s = sig[(sig["issuer"] == issuer) & (sig["date"] < ev) & (sig["date"] >= ev - pd.Timedelta(days=H))]
        if len(s):
            det += 1
            leads.append((ev - s["date"].min()).days)
    return {"defaults_traded": n, "detected": det, "lead_median": float(np.median(leads)) if leads else np.nan}


def table_warning(panel, iss):
    periods = [("2022–2024", pd.Timestamp("2022-01-01"), pd.Timestamp("2024-12-31")),
               ("2025–2026", pd.Timestamp("2025-01-01"), DATA_END)]
    base = price_signals(panel)
    rows = []
    variants = [
        ("correct", "эмитенты, без сигналов после дефолта, полный горизонт", {}),
        ("issues", "считать выпуски, а не эмитентов", {"key": "SECID"}),
        ("post", "оставить сигналы после начала дефолта", {"drop_post": False}),
        ("horizon", "неполный горизонт считать ложной тревогой", {"incomplete": "false"}),
        ("defaulted", "только эмитенты, у которых был дефолт", {"only_defaulted": True}),
    ]
    for code, name, kw in variants:
        for per, a, b in periods:
            r = evaluate(base, iss, a, b, **kw)
            rows.append({"code": code, "variant": name, "period": per, **r})
    warn = pd.DataFrame(rows)
    rec = pd.DataFrame([{"period": per, **recall(base, iss, panel, a, b)} for per, a, b in periods])
    sens = []
    for drop in [0.05, 0.10, 0.15, 0.20, 0.30]:
        s = price_signals(panel, drop=drop)
        for per, a, b in periods:
            sens.append({"drop": drop, "period": per, **evaluate(s, iss, a, b), **recall(s, iss, panel, a, b)})
    return warn, rec, pd.DataFrame(sens)


# ---------------------------------------------------------------- срез для практикума
def cross_section(panel: pd.DataFrame, sec: pd.DataFrame) -> pd.DataFrame:
    x = panel[(panel["date"] == XS_DATE) & (panel["kind"] == "fixed") & (panel["DURATION"] >= 90)
              & panel["g_bp"].notna()].copy()
    x["LISTLEVEL"] = x["SECID"].map(sec.drop_duplicates("SECID").set_index("SECID")["LISTLEVEL"])
    x = x[["date", "SECID", "SHORTNAME", "WAPRICE", "YIELDATWAP", "DURATION", "VALUE", "LISTLEVEL"]]
    x.columns = ["date", "secid", "name", "price_pct", "ytm_pct", "duration_days", "value_rub", "list_level"]
    return x.sort_values("secid").reset_index(drop=True)


def suppress(df: pd.DataFrame, col="issuers") -> pd.DataFrame:
    """Ячейки, где меньше MIN_GROUP эмитентов, обнуляем, чтобы агрегат не раскрывал отдельный выпуск."""
    df = df.copy()
    small = df[col] < MIN_GROUP
    for c in df.columns:
        if c not in ("year", "event", "status", "k", "bucket", "sample", col) and df[c].dtype.kind == "f":
            df.loc[small, c] = np.nan
    return df


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    snap, sec, panel, params, nodes, rd = load_moex()
    sec["issuer"] = "moex:" + sec["EMITTER_ID"].astype("Int64").astype(str)
    kind = coupon_kind(sec, panel)
    panel = panel.merge(sec[["SECID", "issuer"]], on="SECID", how="left")
    panel = panel[panel["issuer"].notna() & (panel["issuer"] != "moex:<NA>")]
    panel["kind"] = panel["SECID"].map(kind).fillna("unknown")
    panel = add_gspread(panel, params, nodes)
    d = load_defaults(sec)
    iss = issuer_first_default(d)

    files = {}
    def save(df, name):
        path = OUT / name
        df.to_parquet(path, index=False)
        files[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(df)}

    ev, by_year, reasons = table_events(d, iss)
    save(suppress(ev), "default_events.parquet")
    save(by_year, "default_years.parquet")
    save(reasons[reasons["issuers"] >= MIN_GROUP], "default_reasons.parquet")
    rd_first = rd.merge(sec[["SECID", "issuer"]], on="SECID").groupby("issuer")["rd_first"].min()
    rd_first = pd.to_datetime(rd_first)
    save(table_rates(panel, sec, iss, rd_first), "default_rates.parquet")
    ims = issuer_month_spreads(panel)
    sp, sp_year, market = table_spreads(ims, iss)
    save(sp, "spread_buckets.parquet")
    save(sp_year, "spread_buckets_year.parquet")
    save(market, "spread_market.parquet")
    save(table_rating_spreads(snap, params), "spread_ratings.parquet")
    paths, path_meta = table_event_paths(panel, iss)
    save(suppress(paths), "event_paths.parquet")
    warn, rec, sens = table_warning(panel, iss)
    save(warn, "warning_variants.parquet")
    save(rec, "warning_recall.parquet")
    save(sens, "warning_thresholds.parquet")
    save(cross_section(panel, sec), "cross_section.parquet")

    meta = {
        "schema_version": 1,
        "built_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "moex_snapshot_id": snap,
        "moex_source": "MOEX ISS via moexutils DuckLake: bonds (TQCB, TQIR, TQRD; RUB), bonds_securities, zcyc_params, indexes_all (RUCBCPAAANS, RUCBCPAANS, RUCBCPANS, RUCBCPBBBNS)",
        "defaults_source": "Cbonds, календарь дефолтов (выгрузки 2022–2024 и 2025–2026); в книге только агрегаты",
        "defaults_period": ["2022-01-01", str(DATA_END.date())],
        "cross_section_date": str(XS_DATE.date()),
        "min_group": MIN_GROUP,
        "issuer_key": "EMITTER_ID карточки MOEX; для выпусков вне биржи – название до запятой",
        "default_date": "первое платёжное событие эмитента (купон, погашение, оферта), если затем был статус «Дефолт» или «Неисполнение оферты»",
        **path_meta,
        "files": files,
    }
    (OUT / "snapshot.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in meta.items() if k != "files"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

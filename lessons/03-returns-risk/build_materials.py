"""Собрать материалы занятия 3 (19 ноября 2026): CSV, графики, слайды с расчётами, ноутбук практики.

Запуск из корня книги:
    python lessons/03-returns-risk/build_materials.py
Работает только с сохранённым снимком data/*-source.parquet (выгрузка: export_source.py).
Ноутбук создаётся заново и без результатов: не запускайте поверх выполненной работы.
Ответов преподавателя здесь нет.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import nbformat as nbf
import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
BOOK = HERE.parents[1]
BOOK_URL = "https://quantviews.github.io/quant-finance-book"
CSV_NAME = "prices_2015_2026.csv"
DATA_URL = ("https://raw.githubusercontent.com/quantviews/quant-finance-book/main/"
            f"lessons/03-returns-risk/data/{CSV_NAME}")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jDm3lILAcKnvIehthge5Q3NfrHSzqmem/edit?usp=sharing"
FORM_URL = "https://forms.gle/fiR6cNu3dRBKVqj49"   # Google-форма сдачи практики 3; None – «способ сдачи объявит преподаватель»

STUDENT_TICKERS = ["AFLT", "ALRS", "BSPB", "CHMF", "FEES", "GAZP", "GMKN", "HYDR", "IRAO", "LKOH",
                   "MAGN", "MOEX", "MTSS", "NLMK", "NVTK", "PHOR", "PIKK", "PLZL", "ROSN", "RUAL",
                   "SBERP", "SIBN", "SNGS", "TATN", "TRNFP"]
TICKERS = sorted(STUDENT_TICKERS + ["SBER"])

BLUE, ORANGE, GREEN, RED, GREY = "#34699A", "#C8702A", "#3F8F5B", "#B8412E", "#64748B"
font_dir = BOOK / "fonts" / "ibm-plex-sans"
for filename in ["IBMPlexSans-Regular.ttf", "IBMPlexSans-SemiBold.ttf"]:
    font_manager.fontManager.addfont(str(font_dir / filename))
plt.rcParams.update({"font.family": "IBM Plex Sans", "font.size": 15,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.spines.bottom": False,
                     "axes.grid": True, "grid.color": "#D6DDE6", "grid.alpha": .65,
                     "axes.axisbelow": True, "svg.fonttype": "path"})

# ---------------------------------------------------------------- данные
source_info = json.loads((HERE / "data" / "source.json").read_text(encoding="utf-8"))
st = pd.read_parquet(HERE / "data" / "stocks-source.parquet")
st["date"] = pd.to_datetime(st["date"])
ix = pd.read_parquet(HERE / "data" / "index-source.parquet")
ix["date"] = pd.to_datetime(ix["date"])
ix = ix.pivot(index="date", columns="ticker", values="close")[["IMOEX", "MCFTR"]]
# Календарь – дни торгов акциями (07.01.2022 у IMOEX есть значение, торгов акциями не было).
calendar = ix.index.intersection(st["date"].unique()).sort_values()
ix = ix.reindex(calendar)

# Ориентир денежного рынка по ставкам RUONIA (как в занятии 1): капитализация в даты
# публикации ставки, простые проценты между ними, база 365/366.
ruonia = pd.read_parquet(HERE / "data" / "ruonia-source.parquet")
ruonia["date"] = pd.to_datetime(ruonia["date"])
ruonia = ruonia.set_index("date")["rate"].sort_index()
assert ruonia.index[0] < calendar[0] and ruonia.index.is_unique
value, anchor, accrual, rate, levels = 1.0, 1.0, 0.0, None, {}
for day in pd.date_range(ruonia.index[0], calendar[-1]):
    if day in ruonia.index:
        anchor, accrual, rate = value, 0.0, ruonia.loc[day] / 100
    levels[day] = value
    accrual += 1 / (366 if day.is_leap_year else 365)
    value = anchor * (1 + rate * accrual)
ru_index = pd.Series(levels).reindex(calendar)
ru_index = 100 * ru_index / ru_index.iloc[0]

adj = st.pivot(index="date", columns="ticker", values="adj_close").reindex(calendar)[TICKERS]
close = st.pivot(index="date", columns="ticker", values="close").reindex(calendar)[TICKERS]
export = pd.concat([ix, ru_index.rename("RUONIA"), adj, close.add_suffix("_close")], axis=1)
export.index.name = "date"
assert export.index.is_unique and ((export > 0) | export.isna()).all().all()
# LF: SHA256 должен совпадать с файлом на GitHub (см. .gitattributes).
csv = export.to_csv(date_format="%Y-%m-%d", float_format="%.6f", lineterminator="\n").encode("utf-8")
(HERE / "data" / CSV_NAME).write_bytes(csv)
sha = hashlib.sha256(csv).hexdigest()

# Дальше – ровно те значения, которые получат студенты.
df = pd.read_csv(HERE / "data" / CSV_NAME, parse_dates=["date"]).set_index("date")
first_day, last_day = df.index[0], df.index[-1]
metadata = {
    "lesson_date": "2026-11-19", "source": source_info["source"],
    "snapshot_built": source_info["exported"],
    "start": str(first_day.date()), "end": str(last_day.date()), "rows": len(df),
    "sha256": sha,
    "fields": {"IMOEX": "индекс Мосбиржи (ценовой)", "MCFTR": "индекс полной доходности",
               "RUONIA": "расчётный индекс денежного рынка по ставкам RUONIA, 100 в первую дату",
               "<TICKER>": "adj_close: с поправкой на сплиты и дивиденды",
               "<TICKER>_close": "close: с поправкой на сплиты, без дивидендов"},
    "notes": ["MCFTR за 24.03.2022 не опубликован в ISS – пропуск оставлен",
              "07.01.2022 исключено: значение IMOEX есть, торгов акциями не было",
              "SIBN загружен из ISS и скорректирован методом moexutils",
              "Пустые ячейки акции – дни без сделок или период до/после торгов"],
}
(HERE / "data" / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
                                             encoding="utf-8")

# ---------------------------------------------------------------- расчёты для слайдов
fmt = lambda x, d=1: f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")
pct = lambda x, d=1: fmt(100 * x, d) + "%"
pp = lambda x, d=1: fmt(100 * x, d) + " п.п."
dt = lambda d: pd.Timestamp(d).strftime("%d.%m.%Y")
period_label = f"{dt(first_day)}–{dt(last_day)}"
years_of = lambda s: (s.index[-1] - s.index[0]).days / 365.25
cagr_of = lambda s: (s.iloc[-1] / s.iloc[0]) ** (1 / years_of(s)) - 1

mcftr = df["MCFTR"].dropna()
imoex = df["IMOEX"]
ru = df["RUONIA"]

# Крючок: вложение в MCFTR на пике 2021 г.
dd_m = mcftr / mcftr.cummax() - 1
peak = mcftr.loc[:"2022-12-31"].idxmax()
trough = dd_m.loc[peak:"2022-12-31"].idxmin()
after = mcftr.loc[trough:]
recovery = after[after >= mcftr.loc[peak]].index[0]
hook = dict(peak=dt(peak), trough=dt(trough), loss=pct(-dd_m.loc[trough]), recovery=dt(recovery),
            months=fmt((recovery - peak).days / 30.44, 0),
            ru_same=pct(ru.loc[recovery] / ru.loc[peak] - 1, 0))

# Асимметрия: 2022 и 2023 гг.
yearly = mcftr.resample("YE").last()
yr = yearly.pct_change()
r22, r23 = yr.loc["2022"].iloc[0], yr.loc["2023"].iloc[0]
two = (1 + r22) * (1 + r23) - 1
need = 1 / (1 + r22) - 1

# Дивидендная отсечка SBER 18.07.2025 (её видели в самостоятельной работе 2).
exd = pd.Timestamp("2025-07-18")
prev = df.index[df.index.get_loc(exd) - 1]
sb_close = df.loc[[prev, exd], "SBER_close"]
sb_adj = df.loc[[prev, exd], "SBER"]
R_close = sb_close.iloc[1] / sb_close.iloc[0] - 1
R_adj = sb_adj.iloc[1] / sb_adj.iloc[0] - 1
div_sber = sb_close.iloc[0] * (1 - (sb_adj.iloc[0] / sb_close.iloc[0]) / (sb_adj.iloc[1] / sb_close.iloc[1]))

# Индексы и денежный рынок за весь период.
cagr_i, cagr_m, cagr_r = cagr_of(imoex), cagr_of(mcftr), cagr_of(ru)
grow = lambda s: 100 * s.iloc[-1] / s.iloc[0]

# Арифметическое и геометрическое среднее годовых доходностей MCFTR.
ann = yr.loc["2016":"2025"]
arith, geom, sd_ann = ann.mean(), (1 + ann).prod() ** (1 / len(ann)) - 1, ann.std()

# Волатильность.
lr = np.log(df[["IMOEX", "MCFTR", "RUONIA"]]).diff()
vol = lr.std() * np.sqrt(252)
vol_day_imoex = lr["IMOEX"].std()
roll = lr["IMOEX"].rolling(63).std() * np.sqrt(252)
roll_max_date, roll_min = roll.idxmax(), roll.min()

# Хвосты: IMOEX.
r_imoex = lr["IMOEX"].dropna()
z = (r_imoex - r_imoex.mean()) / r_imoex.std()
tails = []
for k in [2, 3, 4, 5]:
    tails.append((k, int((z.abs() > k).sum()), len(z) * 2 * stats.norm.sf(k)))
worst = (np.exp(r_imoex) - 1).nsmallest(5)
kurt = r_imoex.kurt()
kurt_ex = r_imoex.drop(pd.Timestamp("2022-02-24")).kurt()   # без одного дня

# Просадки MCFTR.
max_dd, max_dd_date = dd_m.min(), dd_m.idxmin()
share_below = (dd_m < 0).mean()
dd_now = dd_m.iloc[-1]

# Риск и доходность акций студентов.
rows = []
for t in STUDENT_TICKERS + ["SBER"]:
    p = df[t].dropna()
    lr_t = np.log(p).diff().dropna()
    rows.append(dict(ticker=t, cagr=cagr_of(p), vol=lr_t.std() * np.sqrt(252)))
rr = pd.DataFrame(rows).set_index("ticker")
corr_rr = rr.loc[STUDENT_TICKERS, "cagr"].corr(rr.loc[STUDENT_TICKERS, "vol"])
n_beat_m = int((rr.loc[STUDENT_TICKERS, "cagr"] > cagr_m).sum())
n_beat_r = int((rr.loc[STUDENT_TICKERS, "cagr"] > cagr_r).sum())

# Коэффициент Шарпа: дневные простые доходности сверх денежного рынка.
rf = ru.pct_change()
def sharpe(series, start=None, end=None):
    ret = series.pct_change(fill_method=None)
    ex = (ret - rf).loc[start:end].dropna()
    return ex.mean() / ex.std() * np.sqrt(252)
sh_m, sh_i = sharpe(df["MCFTR"]), sharpe(df["IMOEX"])
sh_m_a, sh_m_b = sharpe(df["MCFTR"], None, "2021-12-31"), sharpe(df["MCFTR"], "2022-01-01")
sh_i_a, sh_i_b = sharpe(df["IMOEX"], None, "2021-12-31"), sharpe(df["IMOEX"], "2022-01-01")
y24 = lambda s: s.loc[:"2024-12-31"].dropna().iloc[-1] / s.loc[:"2023-12-31"].dropna().iloc[-1] - 1
m24, r24 = y24(df["MCFTR"]), y24(ru)

# ---------------------------------------------------------------- графики
def finish(fig, ax, name, pctfmt=False):
    if pctfmt:
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{100 * y:.0f}%".replace("-", "−")))
    fig.savefig(HERE / "figures" / name)
    plt.close(fig)

fig, ax = plt.subplots(figsize=(11.8, 4.6), layout="constrained")
for s, label, c in [(imoex, "IMOEX – только цены", BLUE), (mcftr, "MCFTR – с дивидендами", ORANGE),
                    (ru, "RUONIA – денежный рынок", GREEN)]:
    ax.plot(s.index, 100 * s / s.iloc[0], lw=2.2, color=c, label=label)
ax.set_yscale("log")
ax.set_yticks([100, 150, 200, 300, 400], labels=["100", "150", "200", "300", "400"])
ax.set_ylim(90, 480)
ax.minorticks_off()
ax.set_ylabel("100 в начале, лог. шкала")
ax.set_xlim(first_day, last_day)
ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.01))
finish(fig, ax, "total.svg")

fig, ax = plt.subplots(figsize=(11.8, 4.4), layout="constrained")
ax.plot(roll.index, roll, color=BLUE, lw=1.8)
ax.axhline(vol["IMOEX"], color=GREY, lw=.9, ls="--")
ax.text(first_day, vol["IMOEX"], f" за весь период {pct(vol['IMOEX'], 0)}", va="bottom", color=GREY, fontsize=13)
ax.set_xlim(first_day, last_day)
ax.set_ylabel("Годовая волатильность")
finish(fig, ax, "rolling-vol.svg", pctfmt=True)

fig, ax = plt.subplots(figsize=(11.8, 4.4), layout="constrained")
ax.plot(dd_m.index, dd_m, color=RED, lw=1.5)
ax.fill_between(dd_m.index, dd_m, 0, color=RED, alpha=.15)
ax.set_xlim(first_day, last_day)
ax.set_ylabel("От максимума")
finish(fig, ax, "drawdown.svg", pctfmt=True)

fig, ax = plt.subplots(figsize=(11.8, 5.0), layout="constrained")
stu = rr.loc[STUDENT_TICKERS]
ax.scatter(stu["vol"], stu["cagr"], color=BLUE, s=42, zorder=3)
offsets = {"NVTK": (5, -14), "GMKN": (5, -12), "ROSN": (-42, -4)}   # разводим близкие подписи
for t, row in stu.iterrows():
    ax.annotate(t, (row["vol"], row["cagr"]), xytext=offsets.get(t, (5, 3)), textcoords="offset points", fontsize=11, color="#23415F")
ax.scatter([vol["MCFTR"]], [cagr_m], color=ORANGE, s=90, marker="D", zorder=4)
ax.annotate("MCFTR", (vol["MCFTR"], cagr_m), xytext=(6, -14), textcoords="offset points", fontsize=12,
            color=ORANGE, weight="semibold")
ax.axhline(cagr_r, color=GREEN, lw=1.4, ls="--")
ax.text(ax.get_xlim()[1], cagr_r, f"RUONIA {pct(cagr_r)} ", ha="right", va="bottom", color=GREEN, fontsize=12)
ax.axhline(0, color=GREY, lw=.8)
ax.set_xlabel("Годовая волатильность")
ax.set_ylabel("Среднегодовой рост (CAGR)")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{100 * y:.0f}%"))
finish(fig, ax, "risk-return.svg", pctfmt=True)

# Реклама НСЖ: «доходность за срок» делят на число лет.
promo_rows = []
for total, years in [(0.45, 3), (1.00, 5), (2.00, 10), (3.00, 15)]:
    simple, real = total / years, (1 + total) ** (1 / years) - 1
    promo_rows.append(f"| {pct(total, 0)} за {years} {'года' if years < 5 else 'лет'} | {pct(simple, 0)} | "
                      f"{pct(real)} | {fmt(100 * (simple - real), 1)} |")
promo_rows = "\n".join(promo_rows)
promo_cagr = 2 ** (1 / 5) - 1          # 100% за 5 лет
promo_20 = 1.2 ** 5 - 1                # если бы 20% в год со сложным процентом
deposit = 0.16
deposit_5 = (1 + deposit) ** 5 - 1

# Почему геометрическое среднее ниже арифметического: пары доходностей ±x.
drag_rows = []
for x in [0.10, 0.20, 0.50]:
    g = np.sqrt((1 + x) * (1 - x)) - 1          # σ (деление на n) = x, среднее 0
    drag_rows.append(f"| +{pct(x, 0)}, −{pct(x, 0)} | 0% | {pct(g, 2)} | {pct(x ** 2 / 2, 2)} |")
drag_rows = "\n".join(drag_rows)
drag_g20 = np.sqrt(1.2 * 0.8) - 1

# ---------------------------------------------------------------- слайды с расчётами
tail_rows = "\n".join(f"| сильнее {k}σ | {n} | {fmt(e, 1) if e >= 1 else (fmt(e, 2) if e >= .01 else "<0,01")} |" for k, n, e in tails)
worst_rows = "\n".join(f"| {dt(d)} | {pct(v)} |" for d, v in worst.items())
lecture = f'''## Вложение на пике

{hook["peak"]} инвестор вложил 100 руб. в индекс полной доходности MCFTR.

::: {{.columns}}
::: {{.column width="32%"}}
### Худшая точка

::: {{.big}}
−{hook["loss"]}
:::

{hook["trough"]}
:::
::: {{.column width="32%"}}
### Возврат к 100 руб.

::: {{.big}}
{hook["months"]} мес.
:::

{hook["recovery"]}
:::
::: {{.column width="32%"}}
### Денежный рынок

::: {{.big}}
+{hook["ru_same"]}
:::

за тот же срок
:::
:::

::: {{.prompt}}
Хорошее это было вложение? Какими числами вы бы ответили на этот вопрос?
:::

::: {{.source}}
Московская биржа, Банк России; расчёт по дневным закрытиям. До налогов и издержек.
:::

## Почему считаем доходности, а не цены

- Цена акции зависит от числа акций и ничего не говорит о выгоде вложения.
- Инвестора интересует, **на сколько процентов** изменились его деньги.
- Цены «уходят» со временем, их среднее зависит от периода. Доходности колеблются вокруг устойчивого уровня, их можно сравнивать.

**Простая доходность:** R = P<sub>t</sub> / P<sub>t−1</sub> − 1

**Логарифмическая:** r = ln(P<sub>t</sub> / P<sub>t−1</sub>) = ln(1 + R)

::: {{.prompt}}
Цена упала со 100 до 50 руб., затем выросла до 100. Чему равны простые доходности? А логарифмические?
:::

## Падение и рост не компенсируют друг друга

::: {{.columns}}
::: {{.column width="32%"}}
### MCFTR, 2022

::: {{.big}}
{pct(r22)}
:::
:::
::: {{.column width="32%"}}
### MCFTR, 2023

::: {{.big}}
+{pct(r23)}
:::
:::
::: {{.column width="32%"}}
### За два года

::: {{.big}}
{pct(two)}
:::
:::
:::

Чтобы отыграть падение 2022 г., нужен был рост на **{pct(need, 0)}**.

::: {{.prompt}}
(1 − 0,373) × (1 + 0,538) − 1: за два года доходности перемножаются, а не складываются.
:::

::: {{.source}}
Индекс MCFTR на конец года, Московская биржа.
:::

## Какую доходность для чего брать

| | Простая R | Логарифмическая r |
|---|---|---|
| За несколько дней | ∏(1 + R) − 1 | Σ r – простая сумма |
| Портфель из активов | Σ w·R – взвешенная сумма | не складывается |
| Нижняя граница | −100% | −∞ |
| Где применяем | портфели, отчёты, интерпретация | модели рядов, агрегирование во времени |

::: {{.prompt}}
Складываем во времени – логарифмические, складываем по активам – простые.
:::

При малых изменениях ln(1 + R) ≈ R: для обычного дня разница в четвёртом знаке.

## Цена или скорректированная цена

В самостоятельной работе вы нашли разрыв: **{dt(exd)}** – экс-дивидендная дата SBER, дивиденд {fmt(div_sber, 2)} руб.

::: {{.columns}}
::: {{.column width="48%"}}
### По close

::: {{.big}}
{pct(R_close)}
:::

{fmt(sb_close.iloc[0], 2)} → {fmt(sb_close.iloc[1], 2)} руб.
:::
::: {{.column width="48%"}}
### По adj_close

::: {{.big}}
+{pct(R_adj)}
:::

учитывает выплату акционеру
:::
:::

::: {{.small}}
Цены до экс-даты умножаются на 1 − D/P. Корректировка убирает технический эффект выплаты, но не реальные новости: отмена ожидаемого дивиденда (GAZP, 30.06.2022) остаётся падением.
:::

## Без дивидендов рынок выглядит хуже, чем он есть

![](figures/total.svg){{.chart}}

IMOEX: **{pct(cagr_i)}** в год · MCFTR: **{pct(cagr_m)}** · RUONIA: **{pct(cagr_r)}**

::: {{.source}}
{period_label}. Бенчмарк для акций с дивидендами – MCFTR, не IMOEX. RUONIA – расчётный ориентир, не вклад.
:::

## Средняя доходность: какая?

Годовые доходности MCFTR за 2016–2025 гг.

| Среднее | Значение | На какой вопрос отвечает |
|---|---:|---|
| Арифметическое | {pct(arith)} | Оценка доходности одного следующего года |
| Геометрическое (CAGR) | {pct(geom)} | Как в среднем росли деньги инвестора |
| Волатильность годовых доходностей | {pct(sd_ann)} | |

Приближённо: геометрическое ≈ арифметическое − σ²/2. Чем выше волатильность, тем больше разрыв.

::: {{.prompt}}
Какое среднее вы увидите в рекламе инвестиционного продукта?
:::

## Почему геометрическое ниже: пример ±20%

::: {{.columns}}
::: {{.column width="46%"}}
Первый год **+20%**, второй **−20%**. Арифметическое среднее – **0%**.

Капитал: 1,2 × 0,8 = 0,96. Геометрическое среднее: √0,96 − 1 = **{pct(drag_g20, 2)}** в год.

Доходности μ + σ и μ − σ:

(1 + μ + σ)(1 + μ − σ) = (1 + μ)² − σ²

Колебания в любую сторону отнимают σ². Отсюда геометрическое ≈ μ − σ²/2.
:::
::: {{.column width="50%"}}
| Доходности | Арифм. | Геом. | σ²/2 |
|---|---:|---:|---:|
{drag_rows}

::: {{.small}}
σ – с делением на n: для ±20% это 20%. С делением на n − 1 (по умолчанию в pandas) получится 28,3% – это оценка дисперсии по выборке, а не тождество для ряда.
:::
:::
:::

::: {{.prompt}}
У двух акций средняя доходность 10% в год, волатильность 10% и 40%. Какая принесёт больше денег за 10 лет?
:::

## «100% за 5 лет – это 20% в год»?

::: {{.columns}}
::: {{.column width="40%"}}
Так часто описывают программы накопительного страхования жизни (НСЖ). Деление на число лет – это простые проценты: доход прошлых лет не приносит дохода.

**Годовая доходность** = (1 + доходность за срок)<sup>1 / число лет</sup> − 1

100% за 5 лет: 2<sup>1/5</sup> − 1 = **{pct(promo_cagr)} годовых**. При 20% годовых за 5 лет было бы {pct(promo_20)}.
:::
::: {{.column width="56%"}}
| Обещано | «В год» | Реально | Разница, п.п. |
|---|---:|---:|---:|
{promo_rows}

Чем длиннее срок, тем сильнее завышение.
:::
:::

::: {{.prompt}}
Полис: «100% за 5 лет». Вклад: {pct(deposit, 0)} годовых с капитализацией. Что выгоднее?
:::

## Волатильность

**Волатильность** – стандартное отклонение доходностей: насколько они обычно отклоняются от среднего.

Годовая = дневная × √252. Дневная волатильность IMOEX {pct(vol_day_imoex, 2)} → годовая **{pct(vol["IMOEX"])}**.

::: {{.columns}}
::: {{.column width="48%"}}
### Почему корень

Если дневные доходности независимы, дисперсия за 252 дня в 252 раза больше дневной. Стандартное отклонение – в √252 ≈ 15,9 раза.
:::
::: {{.column width="48%"}}
### Другие частоты

Месячные данные: × √12.

Недельные: × √52.

Умножение на 252 – частая ошибка.
:::
:::

## Риск меняется во времени

![](figures/rolling-vol.svg){{.chart}}

::: {{.prompt}}
Большие движения следуют за большими: **кластеры волатильности**.
:::

::: {{.source}}
IMOEX, окно 63 торговых дня (квартал). Пик 2022 г. завышен: изменение за месяц паузы торгов попадает в один день.
:::

## Тяжёлые хвосты

::: {{.columns}}
::: {{.column width="52%"}}
Дни IMOEX с отклонением от среднего:

| Отклонение | Факт | Если бы нормальное |
|---|---:|---:|
{tail_rows}

Избыточный эксцесс: **{fmt(kurt, 0)}**, без 24.02.2022 – **{fmt(kurt_ex, 1)}** (у нормального – 0).
:::
::: {{.column width="44%"}}
Пять худших дней IMOEX:

| Дата | Доходность |
|---|---:|
{worst_rows}
:::
:::

::: {{.source}}
{period_label}, {len(z)} дневных доходностей. Модели с нормальным распределением недооценивают крупные потери.
:::

## Пропуски в данных и пауза 2022 г.

Как устроен снимок занятия:

- **Биржа не работала** (выходные, пауза с 28.02 по 23.03.2022) – строки нет. После 25.02.2022 сразу идёт 24.03.2022, и изменение за месяц выглядит как доходность **одного дня**.
- **Биржа работала, но по бумаге не было сделок** – ячейка пустая. Мы её **не заполняем**: доходность за этот и следующий день тоже будет пустой.

Почему не заполнять прошлой ценой (`ffill`): получится **нулевая** доходность, как будто цена не менялась, а всё движение придёт одним днём позже.

```python
ret = prices.pct_change(fill_method=None)       # пропуск остаётся пропуском
gap = prices.index.to_series().diff().dt.days   # сколько дней между строками
```

::: {{.prompt}}
У MCFTR нет значения за 24.03.2022: биржа его не опубликовала.
:::

## Просадка

![](figures/drawdown.svg){{.chart}}

**Просадка** = цена / максимум к этой дате − 1. Максимальная у MCFTR: **{pct(max_dd)}** ({dt(max_dd_date)}). Ниже прошлого максимума индекс был в {pct(share_below, 0)} дней; сейчас – {pct(dd_now)}.

## Ваши акции: риск и доходность

![](figures/risk-return.svg){{.chart}}

::: {{.small}}
Корреляция волатильности и роста по 25 акциям: **{fmt(corr_rr, 2)}**. Обогнали MCFTR – {n_beat_m} из 25, денежный рынок – {n_beat_r} из 25. {period_label}, по adj_close.
:::

## Доходность с поправкой на риск

**Коэффициент Шарпа** = средняя избыточная доходность / её волатильность.

Избыточная – сверх безрисковой ставки: в России берём денежный рынок (RUONIA).

| | За весь период | до 2022 г. | с 2022 г. |
|---|---:|---:|---:|
| MCFTR | {fmt(sh_m, 2)} | {fmt(sh_m_a, 2)} | {fmt(sh_m_b, 2)} |
| IMOEX | {fmt(sh_i, 2)} | {fmt(sh_i_a, 2)} | {fmt(sh_i_b, 2)} |

2024 г.: MCFTR **{pct(m24)}**, денежный рынок **{pct(r24)}** – и ни одного дня падения.

::: {{.small}}
Дневные доходности сверх RUONIA × √252, {period_label}. Шарп не различает рост и падение и плохо видит редкие крупные потери – его дополняют просадкой.
:::
'''
(HERE / "_lecture.qmd").write_text(lecture, encoding="utf-8")

# ---------------------------------------------------------------- ноутбук
submit = (f"через [Google-форму]({FORM_URL})" if FORM_URL
          else "способом, который объявит преподаватель")
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.metadata.update({"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python"}, "colab": {"name": "practice-03.ipynb"}})
cells = [
md(f'''# Практика 3. Доходность и риск вашей акции
**Количественные финансы · НИУ ВШЭ · 19 ноября 2026**

Продолжаем работать с акцией, которая назначена вам в самостоятельной работе 2 ([таблица распределения]({SHEET_URL})). Сегодня отвечаем на вопрос: **что получил инвестор в эту акцию и каким риском заплатил – по сравнению с рынком и денежным рынком?**

Материал – [глава 4 «Доходность и риск»]({BOOK_URL}/04-returns-risk.html).

| Когда | Задания |
|---|---|
| Вторая пара · 60 минут | 0–4 и 7 |
| Дома | 5, 6, 8, 9 и всё, что не успели |

Сдаём выполненный ноутбук `practice03_фамилия.ipynb` с ответами в ячейках «**Ответ:**» {submit}.

Если застряли больше чем на 10 минут, запишите в ответ, что пробовали, текст ошибки и вопрос, и переходите к следующему заданию.

**Имя и группа:** …

**Моя акция:** …'''),
md('''## 0. Подготовка
Следующие две ячейки подключают библиотеки и загружают данные. Выполните их один раз, редактировать не нужно. Данные загружаются с GitHub; без сети ноутбук читает файл `data/prices_2015_2026.csv` рядом с собой.'''),
code('''import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({"figure.figsize": (10, 4), "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False})
pd.options.display.float_format = "{:.4f}".format
print("Библиотеки загружены")'''),
code(f'''# Загрузка данных: сначала с GitHub, без сети – из файла рядом с ноутбуком.
import hashlib, io, urllib.request
from pathlib import Path

URL = "{DATA_URL}"
LOCAL = Path("data/{CSV_NAME}")
try:
    raw = urllib.request.urlopen(URL, timeout=20).read()
    print("Данные загружены с GitHub")
except OSError:
    raw = LOCAL.read_bytes()
    print("Нет доступа к GitHub, данные прочитаны из файла", LOCAL)
assert hashlib.sha256(raw).hexdigest() == "{sha}", "Файл отличается от снимка занятия"
df = pd.read_csv(io.BytesIO(raw), parse_dates=["date"]).set_index("date")
print("Строк:", len(df), "· период:", df.index.min().date(), "–", df.index.max().date())''',
     metadata={"tags": ["setup"]}),
md(f'''### Что в таблице
Дневные данные за {period_label}, одна строка – один торговый день. Снимок выгружен {dt(source_info["exported"])}; числа могут немного отличаться от примеров книги.

- `IMOEX` – индекс Мосбиржи, только цены. `MCFTR` – индекс полной доходности: те же акции, дивиденды реинвестируются.
- `RUONIA` – расчётный индекс денежного рынка по ставке RUONIA Банка России, 100 в первый день. Это ориентир безрисковой доходности, а не конкретный вклад.
- `SBER`, `GAZP`, … – `adj_close`: цены с поправкой на сплиты и дивиденды.
- `SBER_close`, `GAZP_close`, … – `close`: цены с поправкой на сплиты, без дивидендов.

Пустая ячейка означает, что в этот день сделок с бумагой не было или она ещё (уже) не торговалась. У MCFTR нет значения за 24.03.2022: биржа его не опубликовала. Источник: Московская биржа, Банк России; корректировка на дивиденды – расчёт автора курса.'''),
code('''TICKER = "..."   # ваш тикер, например "GAZP"
assert TICKER in df.columns, "Такого тикера нет в таблице – проверьте написание"
px = df[TICKER]                   # adj_close
px_close = df[TICKER + "_close"]  # close
df[[TICKER, TICKER + "_close", "IMOEX", "MCFTR", "RUONIA"]].tail()'''),
md('''## Задание 1. Паспорт ряда · 10 минут
Прежде чем считать доходности, проверьте ряд своей акции.

1. Первая и последняя даты с ценой, число дней с ценой.
2. Сколько дней в календаре таблицы у вашей акции нет цены и когда они были? Есть ли они в середине ряда, а не только в начале и в конце?
3. Самый большой разрыв между соседними датами с ценой (в календарных днях) и между какими датами он был.

**Ответ:** …'''),
code('''p = px.dropna()
print("С", p.index.min().date(), "по", p.index.max().date(), "· дней с ценой:", len(p))
missing = px.loc[p.index.min():p.index.max()].isna()
print("Пропусков внутри ряда:", missing.sum())
# Найдите самый большой разрыв: p.index.to_series().diff() – разница с предыдущей датой
'''),
md('''## Задание 2. Две доходности · 10 минут
**Сначала предскажите:** в какой день за всю историю простая и логарифмическая доходности вашей акции различались сильнее всего? Это был обычный день?

1. Посчитайте простую `R` и логарифмическую `r` дневные доходности по `adj_close`.
2. Проверьте два тождества на всём ряду: сумма `r` равна `ln(последняя / первая цена)`; произведение `(1 + R)` минус 1 равно `последняя / первая − 1`.
3. Найдите день с наибольшей разницей `R − r` и объясните, почему разница большая именно там.

**Предсказание:** …

**Ответ:** …'''),
code('''R = p.pct_change()            # простая доходность
r = np.log(p).diff()          # логарифмическая
print("Сумма r:", r.sum(), " ln(P_T/P_0):", np.log(p.iloc[-1] / p.iloc[0]))
# Допишите вторую проверку и поиск дня с наибольшей разницей R - r
'''),
md('''## Задание 3. Что дали дивиденды · 15 минут
Среднегодовой темп роста (CAGR) = (последняя / первая цена)^(1 / число лет) − 1.

1. Посчитайте CAGR вашей акции по `close` и по `adj_close` за весь период. Какую часть результата дали дивиденды (в процентных пунктах в год)?
2. Сравните с IMOEX и MCFTR: на сколько п.п. в год различаются они?
3. Найдите три дня, в которые доходность по `adj_close` сильнее всего превышала доходность по `close`. Что это за дни? Проверьте один из них по истории дивидендов (например, на сайте [закрытияреестров.рф](https://закрытияреестров.рф) или у эмитента).

**Ответ:** …'''),
code('''def cagr(series):
    s = series.dropna()
    years = (s.index[-1] - s.index[0]).days / 365.25
    return (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1

print(f"CAGR по adj_close: {cagr(px):.2%}")
# Посчитайте CAGR по close, для IMOEX и MCFTR; найдите три дня с наибольшей разницей доходностей
'''),
md('''## Задание 4. Волатильность · 15 минут
1. Посчитайте годовую волатильность вашей акции, IMOEX и MCFTR по дневным лог-доходностям. Во сколько раз ваша акция волатильнее рынка?
2. Постройте на одном графике скользящую 63-дневную годовую волатильность вашей акции и IMOEX.
3. Найдите периоды, когда волатильность акции была более чем вдвое выше рыночной. С какими событиями в компании или отрасли это связано?

**Внимание к пропускам.** Считайте доходности так, чтобы дни без цены не превращались в нулевые доходности: `np.log(prices).diff()` или `pct_change(fill_method=None)`.

**Ответ:** …'''),
code('''lr = np.log(df[[TICKER, "IMOEX", "MCFTR"]]).diff()
# годовая волатильность: дневное стандартное отклонение × √252
# скользящая: lr.rolling(63).std() * np.sqrt(252)
'''),
md('''## Задание 5. Худшие дни и хвосты · дома, 15 минут
1. Найдите пять худших дней вашей акции по простой доходности `adj_close`.
2. Для каждого дня укажите: доходность IMOEX в тот же день; сколько календарных дней прошло с предыдущей даты с ценой; было ли это падение всего рынка, новость компании, дивидендная отсечка или разрыв в торгах.
3. Сколько дней с отклонением от среднего сильнее 4 стандартных отклонений у вашей акции? При нормальном распределении ожидалось бы `n × 0,0000633` таких дней, где `n` – число доходностей.

**Ответ:** …'''),
code('''ret = df[[TICKER, "IMOEX"]].pct_change(fill_method=None)
gap_days = p.index.to_series().diff().dt.days
# worst = ret[TICKER].nsmallest(5) ...
'''),
md('''## Задание 6. Просадка · дома, 15 минут
Просадка = цена / максимум к этой дате − 1. Максимум берётся только по прошлому: `.cummax()`.

1. Постройте график просадки вашей акции и MCFTR.
2. Найдите максимальную просадку акции: дату пика, дату дна, дату восстановления (если восстановление было). Сколько месяцев длилась просадка?
3. Сравните с MCFTR. Где сейчас ваша акция относительно своего максимума?

**Ответ:** …'''),
code('''dd = px.dropna() / px.dropna().cummax() - 1
# Дата дна: dd.idxmin(); дата пика: последний максимум до дна; восстановление: первая дата после дна, когда цена >= пика
'''),
md('''## Задание 7. Коэффициент Шарпа · 15 минут
Безрисковая дневная доходность – изменение столбца `RUONIA`: `rf = df["RUONIA"].pct_change()`. Избыточная доходность = доходность акции − `rf`. Годовой коэффициент Шарпа = среднее / стандартное отклонение избыточной доходности × √252.

1. Посчитайте коэффициент Шарпа вашей акции и MCFTR за весь период, а также отдельно до 2022 г. и с 2022 г.
2. **Сначала предскажите**, будет ли ваша акция лучше MCFTR в обоих периодах. Затем проверьте.
3. Что оказалось выгоднее за весь период: ваша акция, MCFTR или денежный рынок? Совпадает ли ответ по CAGR и по Шарпу?

**Предсказание:** …

**Ответ:** …'''),
code('''rf = df["RUONIA"].pct_change()

def sharpe(series, start=None, end=None):
    excess = (series.pct_change(fill_method=None) - rf).loc[start:end].dropna()
    return excess.mean() / excess.std() * np.sqrt(252)

print(f"Шарп MCFTR за весь период: {sharpe(df['MCFTR']):.2f}")
# Посчитайте для своей акции и для двух периодов: sharpe(px, None, "2021-12-31"), sharpe(px, "2022-01-01")
'''),
md('''## Задание 8. Проверка кода ИИ-ассистента · дома, 10 минут
Ассистента попросили «посчитать годовую доходность, волатильность, Шарп и максимальную просадку акции». Он написал код ниже. Код работает без ошибок, но числа неверны.

Найдите не меньше трёх ошибок, объясните каждую и исправьте код. Сравните числа до и после исправления.

**Ответ:** …'''),
code('''# Код ассистента – не меняйте эту ячейку, исправленный вариант напишите ниже
price = df[TICKER + "_close"]
ret = price.pct_change().fillna(0)
annual_return = ret.mean() * 252
annual_vol = ret.std() * 252
sharpe_ai = (annual_return - 0.16) / annual_vol
max_drawdown = (price / price.max() - 1).min()
print(f"{annual_return=:.2%} {annual_vol=:.2%} {sharpe_ai=:.2f} {max_drawdown=:.2%}")'''),
code('''# Исправленный код
'''),
md('''## Задание 9. Вывод · дома, 150–250 слов
Ответьте связным текстом: **стоило ли последние годы держать вашу акцию вместо индекса MCFTR или денежного рынка?**

Опирайтесь на свои числа: CAGR, волатильность, максимальную просадку, коэффициент Шарпа. Сравните результат и с инфляцией: реальная доходность = (1 + CAGR) / (1 + π) − 1, где π – среднегодовая инфляция за период (слайд лекции «Номинальная, реальная и долларовая доходность»). Назовите хотя бы одно ограничение вывода (период, налоги и издержки, выбор акции задним числом и т. п.). Числа без объяснения баллов не дают.

Если пользовались ИИ, запишите: **что спросили**, **что получили**, **как проверили**.

**Вывод:** …

**Журнал ИИ:** …'''),
md(f'''## Перед сдачей
- Перезапустите ядро и выполните все ячейки сверху вниз.
- Проверьте, что в каждом задании заполнена ячейка «**Ответ:**».
- Сохраните файл `practice03_фамилия.ipynb` и сдайте его {submit}.

Непонятные строки кода можно разобрать по [приложению A]({BOOK_URL}/appendix-python.html).'''),
]
nb.cells = cells
nbf.validate(nb)
nbf.write(nb, HERE / "practice-03.ipynb")
print(f"CSV: {len(df)} строк, SHA256 {sha}")
print(f"Ноутбук: {len(cells)} ячеек; слайды: _lecture.qmd; графики: figures/")
print(json.dumps(dict(hook=hook, r22=r22, r23=r23, R_close=R_close, R_adj=R_adj, div=div_sber,
                      cagr=[cagr_i, cagr_m, cagr_r], arith=arith, geom=geom, vol=vol.to_dict(),
                      tails=tails, kurt=kurt, kurt_ex=kurt_ex, max_dd=max_dd, corr=corr_rr, beat=[n_beat_m, n_beat_r],
                      sharpe=[sh_m, sh_i, sh_m_a, sh_m_b], y2024=[m24, r24]), default=str, ensure_ascii=False))

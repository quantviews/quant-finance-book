"""Собрать материалы занятия 4 (26 ноября 2026): CSV эмитентов, графики, слайды с расчётами, ноутбук.

Запуск из корня книги:
    python lessons/04-accounting-data/build_materials.py
Читает снимок книги (data/rfsd_*.parquet через qf.data) и data/issuers-source.parquet
(выгрузка: export_issuers.py). Ноутбук создаётся заново и без результатов. Ответов здесь нет.
"""
from pathlib import Path
import hashlib
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import nbformat as nbf
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BOOK = HERE.parents[1]
sys.path.insert(0, str(BOOK))
from qf import data  # noqa: E402

BOOK_URL = "https://quantviews.github.io/quant-finance-book"
RAW = "https://raw.githubusercontent.com/quantviews/quant-finance-book"
# Выборка книги – по закреплённому коммиту: файл не изменится, даже если книгу обновят.
SAMPLE_COMMIT = "6a42857136078f2a01d5e0d85c9d9cf211b14fce"
SAMPLE_URL = f"{RAW}/{SAMPLE_COMMIT}/data/rfsd_sample.parquet"
ISSUERS_CSV = "issuers_2018_2025.csv"
ISSUERS_URL = f"{RAW}/main/lessons/04-accounting-data/data/{ISSUERS_CSV}"
SHEET_URL = "https://docs.google.com/spreadsheets/d/1jDm3lILAcKnvIehthge5Q3NfrHSzqmem/edit?usp=sharing"
FORM_URL = None   # Google-форма сдачи практики 4; None – «способ сдачи объявит преподаватель»
YEAR = 2025
# Версия полного RFSD на Hugging Face (v3), на которой посчитаны материалы
HF_REV = json.loads((BOOK / "data" / "rfsd_snapshot.json").read_text(encoding="utf-8"))["hf_sha"]

STUDENT_TICKERS = ["AFLT", "ALRS", "BSPB", "CHMF", "FEES", "GAZP", "GMKN", "HYDR", "IRAO", "LKOH",
                   "MAGN", "MOEX", "MTSS", "NLMK", "NVTK", "PHOR", "PIKK", "PLZL", "ROSN", "RUAL",
                   "SBERP", "SIBN", "SNGS", "TATN", "TRNFP"]
CLASSES = {"10": "производство пищевых продуктов", "41": "строительство зданий",
           "47": "розничная торговля", "49": "сухопутный и трубопроводный транспорт",
           "62": "разработка программного обеспечения"}
# Класс ОКВЭД для практики: по кругу в алфавитном порядке тикеров, по 5 студентов на класс.
CLASS_OF = {t: list(CLASSES)[i % 5] for i, t in enumerate(STUDENT_TICKERS)}

BLUE, ORANGE, GREEN, RED, GREY = "#34699A", "#C8702A", "#3F8F5B", "#B8412E", "#64748B"
font_dir = BOOK / "fonts" / "ibm-plex-sans"
for filename in ["IBMPlexSans-Regular.ttf", "IBMPlexSans-SemiBold.ttf"]:
    font_manager.fontManager.addfont(str(font_dir / filename))
plt.rcParams.update({"font.family": "IBM Plex Sans", "font.size": 15,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.spines.bottom": False,
                     "axes.grid": True, "grid.color": "#D6DDE6", "grid.alpha": .65,
                     "axes.axisbelow": True, "svg.fonttype": "path"})

fmt = lambda x, d=1: f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")
pct = lambda x, d=1: fmt(100 * x, d) + "%"
bn = lambda x, d=1: fmt(x / 1e6, d)            # тыс. руб. -> млрд руб.
def times(x):
    n = round(x)
    w = "раза" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "раз"
    return f"в {n} {w}"
tn = lambda x, d=2: fmt(x / 1e9, d)            # тыс. руб. -> трлн руб.

# ---------------------------------------------------------------- данные: выборка книги
sample_bytes = (BOOK / "data" / "rfsd_sample.parquet").read_bytes()
sample_sha = hashlib.sha256(sample_bytes).hexdigest()
assert sample_sha == "9b0171a181556c0df0db07397f49a2017b2f25b2108403318f95394203c7557a", \
    "data/rfsd_sample.parquet изменился: обновите SAMPLE_COMMIT и контрольную сумму"
rfsd = data.load_rfsd()

# Parquet и CSV на выборке книги: размер, время чтения, ИНН с ведущим нулём.
import io as _io, time as _time  # noqa: E401,E402
csv_bytes = rfsd.to_csv(index=False).encode("utf-8")
def _best(fn, n=5):
    out = []
    for _ in range(n):
        t = _time.perf_counter(); fn(); out.append(_time.perf_counter() - t)
    return min(out)
pq_path = BOOK / "data" / "rfsd_sample.parquet"
pqcsv = dict(
    csv_mb=len(csv_bytes) / 1e6, pq_mb=len(sample_bytes) / 1e6,
    t_csv=_best(lambda: pd.read_csv(_io.BytesIO(csv_bytes), low_memory=False)),
    t_pq=_best(lambda: pd.read_parquet(pq_path)),
    t_pq5=_best(lambda: pd.read_parquet(pq_path, columns=["inn", "year", "okved", "filed", "line_2110"])),
    zero_inn=int(rfsd.loc[rfsd["inn"].str.startswith("0"), "inn"].nunique()),
    nrow=len(rfsd), ncol=rfsd.shape[1])
# Полный RFSD v3, год 2025 (локальная копия, метаданные parquet-файла)
FULL = dict(mb=534, rows=3.14, cols=223, groups=1933, filed=2.02, sel_mb=63)
rfsd["div"] = rfsd["okved"].str[:2]

# ---------------------------------------------------------------- данные: эмитенты акций курса
src_info = json.loads((HERE / "data" / "issuers-source.json").read_text(encoding="utf-8"))
iss = pd.read_parquet(HERE / "data" / "issuers-source.parquet")
iss_cols = ["ticker", "issuer", "inn", "year", "okved", "filed", "imputed", "outlier",
            "line_1250", "line_1300", "line_1410", "line_1510", "line_1600", "line_1700",
            "line_2110", "line_2120", "line_2200", "line_2300", "line_2310", "line_2330", "line_2400",
            "line_4100", "line_4500"]
iss_csv = iss[iss_cols].to_csv(index=False, float_format="%.0f", lineterminator="\n").encode("utf-8")
(HERE / "data" / ISSUERS_CSV).write_bytes(iss_csv)
iss_sha = hashlib.sha256(iss_csv).hexdigest()
iss = pd.read_csv(HERE / "data" / ISSUERS_CSV, dtype={"inn": str})
(HERE / "data" / "metadata.json").write_text(json.dumps({
    "lesson_date": "2026-11-26",
    "issuers": {"file": ISSUERS_CSV, "sha256": iss_sha, "rows": len(iss),
                "source": src_info["source"], "rfsd_sha": src_info["sha"],
                "fields": "ticker, issuer, inn, year, флаги RFSD (filed, imputed, outlier), строки форм в тыс. руб.; расходы отрицательные",
                "notes": ["ИНН – головная компания-эмитент, отчётность РСБУ отдельного юрлица, не группы",
                          "Строка без значений: отчётность не раскрыта или организации нет в RFSD (банки, Мосбиржа)",
                          "SBER и SBERP – один эмитент"]},
    "sample": {"url": SAMPLE_URL, "sha256": sample_sha,
               "description": "выборка книги: классы ОКВЭД 10, 41, 47, 49, 62, выручка ≥ 1 млрд руб. хотя бы в одном году 2018–2025"},
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- расчёты для слайдов
cases = data.load_rfsd_cases()
case = lambda inn, y: cases[(cases["inn"] == inn) & (cases["year"] == y)].iloc[0]
mg, td = case("2309085638", 2023), case("2310031475", 2023)
td25 = case("2310031475", YEAR)
summary = data.load_rfsd_summary().set_index("year")
s25 = summary.loc[YEAR]
hid = data.load_rfsd_hidden().set_index("year")
hid_share = hid.loc[YEAR, "hidden"] / hid.loc[YEAR, "large"]
hid_rev = hid.loc[YEAR, "hidden_revenue"] / hid.loc[YEAR, "revenue"]

rs = data.load_rosstat_revenue()
rf = data.load_rfsd_revenue_okved()
head = rs[rs["okved"] == "101.АГ"].set_index("year")["revenue"]
coverage = (rf.groupby("year")["revenue"].sum() / head).dropna().loc[2018:]
m = rf.merge(rs, on=["okved", "year"], suffixes=("_rfsd", "_rosstat"))
m["cov"] = m["revenue_rfsd"] / m["revenue_rosstat"]
cls_cov = m[m["year"] == YEAR].set_index("okved")["cov"]

# Эмитенты: кто есть в RFSD за последний год
last = iss[iss["year"] == YEAR].drop_duplicates("inn").set_index("ticker")
banks = ["SBER", "BSPB"]
absent = [t for t in last.index if t not in banks and pd.isna(last.loc[t, "okved"])]
open_ = sorted(last.index[last["filed"] == 1])
hidden_ = sorted(t for t in last.index if t not in banks + absent + open_)
n_issuers = len(last)
ever = iss[iss["filed"] == 1].groupby("ticker")["year"].max()
hidden_since = {t: int(ever.get(t, 0)) for t in hidden_}

irao = iss[(iss["ticker"] == "IRAO") & (iss["year"] == YEAR)].iloc[0]
gazp = iss[(iss["ticker"] == "GAZP") & (iss["year"] == YEAR)].iloc[0]
aflt = iss[(iss["ticker"] == "AFLT") & (iss["year"] == 2023)].iloc[0]
aflt_roe = aflt["line_2400"] / aflt["line_1300"]

# Выборка: коэффициенты по классам
okved_change = float((rfsd.groupby("inn")["okved"].nunique() > 1).mean())
d = rfsd[(rfsd["year"] == YEAR) & (rfsd["filed"] == 1)].copy()
pos = lambda x: x.where(x > 0)
d["ros"] = d["line_2400"] / pos(d["line_2110"])
d["roa"] = d["line_2400"] / pos(d["line_1600"])
d["roe"] = d["line_2400"] / pos(d["line_1300"])
d["turnover"] = d["line_2110"] / pos(d["line_1600"])
d["current"] = d["line_1200"] / pos(d["line_1500"])
d["ebit"] = d["line_2300"] - d["line_2330"].fillna(0)
d["coverage"] = d["ebit"] / pos(-d["line_2330"])
med = d.groupby("div")[["ros", "roa", "roe", "turnover", "current", "coverage"]].median()
n_div = d.groupby("div").size()
fa = (d["line_1150"] / pos(d["line_1600"])).groupby(d["div"]).median()
roe = d["roe"].dropna()
roe_q = roe.quantile([0.01, 0.99])
neg_eq = float(s25["nonpositive_equity"]) / float(s25["filed"])
mism = float(s25["balance_mismatch"]) / float(s25["with_balance"])
both = d[d["line_4500"].notna() & d["line_1250"].notna()]
cash_match = float(((both["line_4500"] - both["line_1250"]).abs() <= 5).mean())
flows = d.groupby("div").agg(profit=("line_2400", lambda x: (x > 0).mean()),
                             cfo=("line_4100", lambda x: (x > 0).mean()))

# ---------------------------------------------------------------- графики
def finish(fig, name):
    fig.savefig(HERE / "figures" / name)
    plt.close(fig)

fig, ax = plt.subplots(figsize=(11.8, 4.6), layout="constrained")
h = hid.loc[2018:]
ax.bar(h.index, h["hidden"], color=BLUE, width=.65)
ax.set_ylabel("Число компаний")
ax2 = ax.twinx()
ax2.plot(h.index, h["hidden_revenue"] / h["revenue"], color=RED, marker="o", lw=2.2)
ax2.set_ylim(0, .5)
ax2.grid(False)
ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{100 * y:.0f}%"))
ax2.set_ylabel("Доля в выручке крупных компаний", color=RED)
for sp in ax2.spines.values():
    sp.set_visible(False)
finish(fig, "hidden.svg")

fig, ax = plt.subplots(figsize=(11.8, 6.2), layout="constrained")
top = m[m["year"] == YEAR].nlargest(20, "revenue_rosstat").sort_values("cov")
labels = top["okved"] + " " + top["name"].str.slice(0, 40)
ax.barh(labels, top["cov"], color=np.where(top["cov"] < .5, RED, BLUE))
ax.axvline(1, color=GREY, lw=.9, ls=":")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{100 * x:.0f}%"))
ax.tick_params(axis="y", labelsize=12)
finish(fig, "coverage.svg")

fig, ax = plt.subplots(figsize=(11.8, 4.5), layout="constrained")
ax.hist(roe.clip(-1, 2), bins=80, color=BLUE)
ax.axvline(roe.median(), color=RED, lw=2, label=f"медиана {pct(roe.median(), 0)}")
ax.plot([], [], " ", label=f"среднее {pct(roe.mean(), 0)} – за пределами шкалы")
ax.set_xlabel("ROE; значения ниже −100% и выше 200% прижаты к краям")
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{100 * x:.0f}%".replace("-", "−")))
ax.legend(frameon=False)
finish(fig, "roe.svg")

# ---------------------------------------------------------------- слайды с расчётами
SHORT = {"10": "пищевые продукты", "41": "строительство", "47": "розница", "49": "транспорт", "62": "разработка ПО"}
med_rows = "\n".join(
    f"| {k} {SHORT[k]} | {n_div[k]} | {pct(med.loc[k, 'ros'])} | {fmt(med.loc[k, 'turnover'], 2)} | "
    f"{pct(med.loc[k, 'roa'])} | {pct(med.loc[k, 'roe'], 0)} | {fmt(med.loc[k, 'current'], 2)} |"
    for k in CLASSES)
top_div, low_div = med["ros"].idxmax(), med["ros"].idxmin()
flow_rows = "\n".join(f"| {k} {SHORT[k]} | {pct(flows.loc[k, 'profit'], 0)} | {pct(flows.loc[k, 'cfo'], 0)} |"
                      for k in CLASSES)
tick_list = lambda ts: ", ".join(ts)
hidden_rows = ", ".join(f"{t} ({hidden_since[t]})" if hidden_since[t] else f"{t} (–)" for t in hidden_)

lecture = f'''## Выручка «Магнита» – меньше миллиарда?

::: {{.columns}}
::: {{.column width="32%"}}
### ПАО «Магнит», выручка

::: {{.big}}
{bn(mg["line_2110"], 2)} млрд
:::

2023 г.
:::
::: {{.column width="32%"}}
### ПАО «Магнит», прибыль

::: {{.big}}
{bn(mg["line_2400"], 1)} млрд
:::

из них дивиденды дочерних компаний – {bn(mg["line_2310"], 1)} млрд
:::
::: {{.column width="32%"}}
### АО «Тандер», выручка

::: {{.big}}
{tn(td["line_2110"])} трлн
:::

дочерняя компания: магазины сети
:::
:::

::: {{.prompt}}
Ошибка в данных? Как прибыль может быть в сто раз больше выручки?
:::

::: {{.source}}
RFSD, отчётность за 2023 г., млрд руб.
:::

## Отчётность юрлица, а не группы

- **ПАО «Магнит»** – холдинг: владеет другими компаниями, сам почти ничего не продаёт.
- Магазины принадлежат дочерней компании **АО «Тандер»**.
- Прибыль холдинга – дивиденды дочерних компаний: строка 2310 «Доходы от участия».
- В {YEAR} г. «Тандер» получил убыток ({bn(td25["line_2400"], 1)} млрд руб.) → дивидендов нет → прибыль «Магнита» – {bn(case("2309085638", YEAR)["line_2400"], 1)} млрд руб.

::: {{.columns}}
::: {{.column width="48%"}}
**РСБУ** – российские стандарты: отчётность **одного юрлица**. Это и есть RFSD.
:::
::: {{.column width="48%"}}
**МСФО** – международные стандарты: отчётность **всей группы**, сделки внутри группы исключены.
:::
:::

::: {{.prompt}}
Прежде чем анализировать компанию, выясните, какое юрлицо ведёт основной бизнес.
:::

## Откуда берётся отчётность

- Каждая организация раз в год сдаёт бухгалтерскую отчётность в налоговую (ФНС).
- С 2019 г. отчёты открыты в **ГИР БО**: [bo.nalog.gov.ru](https://bo.nalog.gov.ru/).
- Банки и страховщики отчитываются перед Банком России – в наборе их нет.
- **RFSD** – эти отчёты за 2011–{YEAR} гг., собранные в одну очищенную таблицу. Делает Европейский университет в Санкт-Петербурге.

::: {{.columns}}
::: {{.column width="32%"}}
::: {{.big}}
{fmt(s25["firms"] / 1e6, 1)} млн
:::
организаций в {YEAR} г.
:::
::: {{.column width="32%"}}
::: {{.big}}
{fmt(s25["filed"] / 1e6, 1)} млн
:::
подали отчётность
:::
::: {{.column width="32%"}}
::: {{.big}}
{fmt(s25["with_revenue"] / 1e6, 1)} млн
:::
с выручкой больше нуля
:::
:::

::: {{.source}}
RFSD v3 (Bondarkov, Ledenev, Skougarevskiy, 2025), лицензия CC BY 4.0, данные на Hugging Face.
:::

## Ваши акции: кто есть в RFSD?

{n_issuers} эмитентов акций курса. Отчётность за {YEAR} г.:

| Отчётность | Эмитенты |
|---|---|
| Открыта: **{len(open_)}** | {tick_list(open_)} |
| Скрыта: **{len(hidden_)}** (в скобках – последний открытый год) | {hidden_rows} |
| Нет в RFSD: банки и биржа | SBER, SBERP, BSPB, MOEX – отчитываются перед Банком России |

::: {{.prompt}}
Большинство «голубых фишек» по открытым данным не изучить. Что это значит для выводов об отрасли?
:::

::: {{.source}}
«–» – не открыта ни разу за 2018–{YEAR} гг. До 2019 г. RFSD берёт данные Росстата, поэтому у части эмитентов виден только 2018 г.
:::

## Три формы отчётности

::: {{.columns}}
::: {{.column width="32%"}}
### Баланс

Что есть у компании на конец года.

Активы = капитал + обязательства.

Строки 1100–1700.
:::
::: {{.column width="32%"}}
### Финансовые результаты

Как из выручки получается чистая прибыль.

Строки 2110–2400.
:::
::: {{.column width="32%"}}
### Движение денег

Сколько денег реально пришло и ушло: от основной работы, инвестиций и займов.

Строки 4100–4500.
:::
:::

::: {{.prompt}}
Прибыль – это не деньги: продажу записывают сразу, а оплата может прийти позже.
:::

## Строка формы – столбец таблицы

| Код | Строка | | Код | Строка |
|---|---|---|---|---|
| 1100 / 1200 | Внеоборотные / оборотные активы | | 2110 | Выручка |
| 1250 | Денежные средства | | 2120 | Себестоимость продаж |
| 1300 | Капитал | | 2200 | Прибыль от продаж |
| 1410 / 1510 | Займы: долгие / короткие | | 2310 | Доходы от участия |
| 1500 | Краткосрочные обязательства | | 2330 | Проценты к уплате |
| 1600 = 1700 | Итого активы = пассивы | | 2300 / 2400 | Прибыль до налогов / чистая |

::: {{.small}}
В RFSD это столбцы `line_1600`, `line_2110` и т. д. Справочник строк – `rfsd_lines.csv` в данных книги.
:::

## Два соглашения

::: {{.columns}}
::: {{.column width="48%"}}
### Тысячи рублей

Выручка «Тандера» за {YEAR} г. в данных: **{fmt(td25["line_2110"], 0)}**.

Это {tn(td25["line_2110"])} трлн руб.
:::
::: {{.column width="48%"}}
### Расходы – со знаком минус

Себестоимость и проценты к уплате хранятся отрицательными.

- Валовая прибыль = `line_2110 + line_2120`.
- EBIT = `line_2300 − line_2330`.
:::
:::

::: {{.prompt}}
`line_2110 = 500 000`, `line_2120 = −380 000`. Валовая прибыль в рублях? Что даст `line_2110 − line_2120`?
:::

::: {{.small}}
В старых версиях RFSD знаки расходов были разными. Перед расчётом проверьте знак себестоимости и процентов.
:::

## Формат parquet

RFSD хранится в формате **parquet**, а не CSV.

::: {{.columns}}
::: {{.column width="57%"}}
- **По столбцам:** нужны 7 столбцов из 223 – читаются только они.
- **Сжатие:** файл в несколько раз меньше CSV.
- **Типы внутри файла:** ИНН остаётся текстом, дата – датой.
- **Пропуск лишнего:** для каждого блока строк записаны min и max; блоки без нужных значений не читаются.
- **Деление по годам:** папки `year=2018/`, `year=2019/`…
:::
::: {{.column width="39%"}}
| RFSD, {YEAR} г. | |
|---|---:|
| Файл | {FULL["mb"]} МБ |
| Строк | {fmt(FULL["rows"], 2)} млн |
| Столбцов | {FULL["cols"]} |
| Блоков строк | {fmt(FULL["groups"], 0)} |
| 7 нужных столбцов | ≈{FULL["sel_mb"]} МБ |
:::
:::

::: {{.small}}
Весь RFSD за 2011–{YEAR} гг. – около 8 ГБ.
:::

## Parquet и CSV: выборка книги

Выборка книги: {fmt(pqcsv["nrow"] / 1e3, 0)} тыс. строк, {pqcsv["ncol"]} столбец.

| | CSV | Parquet |
|---|---|---|
| Размер файла | {fmt(pqcsv["csv_mb"], 1)} МБ | {fmt(pqcsv["pq_mb"], 1)} МБ |
| Чтение всей таблицы | {times(pqcsv["t_csv"] / pqcsv["t_pq"])} дольше | за долю секунды |
| Чтение 5 столбцов | только весь файл целиком | {times(pqcsv["t_pq"] / pqcsv["t_pq5"])} быстрее всей таблицы |
| ИНН `0101000776` | число 101000776: **ноль потерян** | текст, как в данных |

- У {pqcsv["zero_inn"]} компаний выборки ИНН начинается с нуля. После CSV их не найти по ИНН.
- CSV – для небольших таблиц и Excel. Для анализа – parquet.

## pandas и Polars

Обе библиотеки работают с таблицами. Разница – как они читают и считают.

| | pandas | Polars |
|---|---|---|
| Когда считает | сразу, на каждой строке кода | можно отложить: сначала план, потом `collect()` |
| Что держит в памяти | всю таблицу | только нужные столбцы и строки |
| Ядра процессора | одно | все |
| Где удобнее | статистика, графики, примеры в интернете | большие файлы |

::: {{.columns}}
::: {{.column width="45%"}}
```python
d = pd.read_parquet(f)
d = d[d["filed"] == 1]
d["line_2110"].median()
```
:::
::: {{.column width="52%"}}
```python
(pl.scan_parquet(f)
   .filter(pl.col("filed") == 1)
   .select(pl.col("line_2110").median())
   .collect())
```
:::
:::

::: {{.prompt}}
Polars – достать данные из большого файла, pandas – считать на полученной таблице.
:::

## Ленивый запрос в Polars

`scan_parquet` ничего не читает, а только записывает план. `collect()` выполняет план: читает нужные столбцы и отбирает строки прямо при чтении.

```python
import polars as pl
lf = pl.scan_parquet("rfsd_sample.parquet")              # ничего не прочитано
top = (lf.filter((pl.col("year") == {YEAR}) & (pl.col("filed") == 1)
                 & pl.col("okved").str.starts_with("47"))
         .select("name", "inn", "line_2110", "line_2400")
         .sort("line_2110", descending=True, nulls_last=True)
         .head(5))
top.explain()      # показать план
top.collect()      # выполнить
```

::: {{.small}}
`nulls_last=True`: иначе при сортировке по убыванию первыми окажутся компании без выручки.
:::

## Полный RFSD: два способа

::: {{.columns}}
::: {{.column width="49%"}}
### А. Прямо с Hugging Face

```python
url = ("hf://datasets/irlspbru/RFSD/"
       "RFSD/year={YEAR}/part-0.parquet")
lf = pl.scan_parquet(url)
```

- Скачиваются только нужные столбцы, ≈{FULL["sel_mb"]} МБ.
- При каждом запуске – заново, нужен интернет.
:::
::: {{.column width="49%"}}
### Б. Скачать файл один раз

```python
url = ("https://huggingface.co/datasets/"
       "irlspbru/RFSD/resolve/main/"
       "RFSD/year={YEAR}/part-0.parquet")
f = "data/rfsd_{YEAR}.parquet"
urllib.request.urlretrieve(url, f)
lf = pl.scan_parquet(f)
```

- {FULL["mb"]} МБ на диск один раз.
- Дальше – быстро и без интернета.
:::
:::

```python
my = (lf.filter((pl.col("filed") == 1) & pl.col("okved").str.starts_with("10.51"))
        .select("inn", "okved", "region", "line_2110", "line_2400", "line_1600")
        .collect())
my.write_parquet("data/my_industry.parquet")      # дальше работаем с этим файлом
```

::: {{.small}}
- В полном RFSD **нет названий компаний** – ищите по ИНН в ГИР БО. Нет и столбца `year`: год – в имени папки.
- Если Hugging Face не открывается из вашей сети – запускайте в Google Colab.
:::

## Классификатор ОКВЭД

ОКВЭД – код вида деятельности. Чем длиннее код, тем уже отрасль:

| Код | Что это |
|---|---|
| 47 | Розничная торговля |
| 47.1 | …в неспециализированных магазинах |
| 47.11 | …в основном продуктами: продуктовые сети |

- В RFSD у компании один, **основной** код. Реальный бизнес бывает шире.
- У **{pct(okved_change, 0)}** компаний выборки основной код менялся за 2018–{YEAR} гг.
- Холдинги часто записаны как «головные офисы» (70) или финансы (64), а не по отрасли бизнеса.

::: {{.prompt}}
Код за какой год брать для отбора? Решите и запишите правило до расчётов.
:::

## Демо: ОКВЭД 2 в rustata

[rustata.ru/classifier/okved2](https://rustata.ru/classifier/okved2) – дерево кодов и статистика Росстата по каждому коду.

::: {{.columns}}
::: {{.column width="44%"}}
### Код 47.11 – продуктовые сети

Внутри три кода:

- 47.11.1 – замороженные продукты;
- 47.11.2 – незамороженные продукты, напитки, табак;
- 47.11.3 – широкий ассортимент, в основном продукты.
:::
::: {{.column width="52%"}}
### Что Росстат даёт по коду

- выручка организаций;
- число организаций;
- рентабельность продаж;
- прибыль, убытки убыточных;
- число работников, инвестиции.
:::
:::

::: {{.prompt}}
Для проекта: найдите свой код и сравните выручку в RFSD с Росстатом. Какую часть отрасли вы видите?
:::

## Финансовые коэффициенты

| Коэффициент | Формула в RFSD | Что показывает |
|---|---|---|
| Рентабельность продаж (ROS) | 2400 / 2110 | прибыль с рубля выручки |
| Рентабельность активов (ROA) | 2400 / 1600 | прибыль с рубля активов |
| Рентабельность капитала (ROE) | 2400 / 1300 | прибыль с рубля денег собственников |
| Оборачиваемость активов | 2110 / 1600 | выручка с рубля активов |
| Текущая ликвидность | 1200 / 1500 | хватит ли оборотных активов на короткие долги |
| Покрытие процентов | (2300 − 2330) / (−2330) | во сколько раз прибыль до процентов и налогов (EBIT) больше процентов |

::: {{.prompt}}
Делим только на положительное: при капитале или выручке ≤ 0 отношение теряет смысл.
:::

## Сначала предскажите

Выборка книги: компании пяти классов ОКВЭД с выручкой от 1 млрд руб. хотя бы в одном году 2018–{YEAR}.

- 10 – производство пищевых продуктов
- 41 – строительство зданий
- 47 – розничная торговля
- 49 – сухопутный транспорт
- 62 – разработка программного обеспечения

::: {{.prompt}}
Где медианная рентабельность продаж выше всего? Где ниже всего? Где выше оборачиваемость активов?
:::

## Медианы по классам, {YEAR} г.

| Класс | Отчётов | ROS | Оборач. | ROA | ROE | Ликв. |
|---|---:|---:|---:|---:|---:|---:|
{med_rows}

::: {{.small}}
- Маржа выше всего в классе **{top_div}**, ниже всего – в **{low_div}**.
- Розница: маржа низкая, но активы оборачиваются быстро. Разработчику ПО почти не нужны активы.
- ROS × оборачиваемость = ROA – начало разложения DuPont (глава 6).
:::

::: {{.source}}
Выборка RFSD, поданные отчёты за {YEAR} г.; знаменатели только положительные.
:::

## Капитал меньше нуля: ROE из убытка

::: {{.columns}}
::: {{.column width="48%"}}
ПАО «Аэрофлот», 2023 г.:

- чистая прибыль **{bn(aflt["line_2400"], 1)} млрд руб.** (убыток);
- капитал **{bn(aflt["line_1300"], 1)} млрд руб.**;
- «ROE» = {bn(aflt["line_2400"], 1)} / ({bn(aflt["line_1300"], 1)}) = **+{pct(aflt_roe, 0)}**.
:::
::: {{.column width="48%"}}
- В полном RFSD за {YEAR} г. капитал ≤ 0 у **{pct(neg_eq, 0)}** поданных отчётов.
- Чаще всего это мелкие фирмы с накопленными убытками.
- ROE и долг/капитал для них не считаем.
:::
:::

::: {{.prompt}}
Поэтому в коде делим только на положительное: `x.where(x > 0)`.
:::

## Медиана, а не среднее

![](figures/roe.svg){{.chart}}

::: {{.small}}
- У 1% компаний ROE ниже {pct(roe_q.iloc[0], 0)}, у 1% – выше {pct(roe_q.iloc[1], 0)}: капитал у них почти нулевой.
- Несколько таких компаний сдвигают среднее. Поэтому сравниваем медианы и квартили.
- Другой способ – **винсоризация**: крайние значения заменяют на 1-й и 99-й процентили.
:::

## EBITDA по RFSD не посчитать

EBITDA = EBIT + амортизация. Амортизации в RFSD нет:

- в отчёте о результатах она спрятана внутри себестоимости;
- отчёт о движении денег по РСБУ показывает только платежи, а амортизация – не платёж;
- пояснения к отчётности, где она есть, в RFSD не входят.

Ошибка больше там, где много основных средств: медиана **{pct(fa["49"], 0)}** активов у транспорта против **{pct(fa["62"], 0)}** у разработчиков ПО.

::: {{.prompt}}
Нет показателя в данных – так и пишем. EBIT называем EBIT. EBITDA публичных компаний берём из МСФО.
:::

## Качество данных: что проверять

| Проверка | Как | Полный RFSD, {YEAR} г. |
|---|---|---|
| Баланс сходится | 1600 = 1700 | не сходится у {pct(mism, 2)} |
| Капитал положителен | 1300 > 0 | ≤ 0 у {pct(neg_eq, 0)} |
| Деньги в двух формах | 4500 = 1250 | совпадают у {pct(cash_match, 0)} (выборка) |
| Отчёт подан | `filed = 1` | иначе значения восстановлены или отчёта нет |
| Подозрительный отчёт | `outlier = 1` | пометка авторов RFSD |

::: {{.small}}
- С {YEAR} г. новые формы отчётности: часть кодов строк изменилась.
- За последний год RFSD ещё не восстанавливает пропуски.
:::

## Скрытая отчётность

![](figures/hidden.svg){{.chart}}

::: {{.small}}
- Столбцы – крупные компании (выручка от 10 млрд руб.), скрывшие отчётность; линия – их доля в выручке.
- В {YEAR} г. скрыли отчётность {fmt(hid.loc[YEAR, "hidden"], 0)} из {fmt(hid.loc[YEAR, "large"], 0)} крупных компаний ({pct(hid_share, 0)}), это {pct(hid_rev, 0)} их выручки.
- Скачок в 2019 г.: RFSD перешёл с данных Росстата на ГИР БО.
:::

## Какую часть отрасли мы видим

![](figures/coverage.svg){{.chart}}

::: {{.small}}
- Выручка компаний в RFSD к выручке отрасли по Росстату (rustata), {YEAR} г.
- В целом по экономике видим {pct(coverage.loc[2018], 0)} в 2018 г. и {pct(coverage.loc[YEAR], 0)} в {YEAR} г.
- Больше 100% – коды отраслей в двух источниках не совпадают.
:::

## Холдинги среди наших эмитентов

| Эмитент, {YEAR} г. | Выручка | Доходы от участия | Чистая прибыль |
|---|---:|---:|---:|
| ПАО «Интер РАО» | {bn(irao["line_2110"], 1)} | {bn(irao["line_2310"], 1)} | {bn(irao["line_2400"], 1)} |
| ПАО «Газпром» | {fmt(gazp["line_2110"] / 1e6, 0)} | {bn(gazp["line_2310"], 0)} | {bn(gazp["line_2400"], 1)} |

::: {{.small}}
- Млрд руб., отчётность головной компании по РСБУ.
- «Интер РАО»: выручка группы по МСФО – больше 1 трлн руб. Электростанции и сбыт – в дочерних компаниях.
- «Газпром»: видна продажа газа, но не нефть («Газпром нефть») и не электроэнергия группы.
:::

::: {{.prompt}}
Для вашей акции: чья отчётность в RFSD – группы или одного юрлица?
:::

## Прибыль и деньги

| Класс | С прибылью | С притоком денег от основной работы |
|---|---:|---:|
{flow_rows}

::: {{.small}}
- Доля поданных отчётов {YEAR} г. Приток денег – строка 4100 больше нуля.
- Застройщики тратят деньги годами, а прибыль показывают при сдаче дома.
- С 2019 г. деньги покупателей квартир лежат на эскроу-счетах до сдачи дома.
:::

## Две ошибки в учебных работах

::: {{.columns}}
::: {{.column width="48%"}}
### Корреляция уровней

«Выручка и прибыль коррелируют на 0,7» – значит только, что крупные компании крупны во всём.

Связи ищем в отношениях (маржа, долговая нагрузка) и в изменениях.
:::
::: {{.column width="48%"}}
### Рост в текущих рублях

Отчётность – в рублях своего года. При инфляции 7–12% рост выручки на 10% – почти нулевой реальный рост.

Сравниваем с инфляцией и с отраслью за тот же год.
:::
:::
'''
(HERE / "_lecture.qmd").write_text(lecture, encoding="utf-8")

# ---------------------------------------------------------------- ноутбук
submit = (f"через [Google-форму]({FORM_URL})" if FORM_URL
          else "способом, который объявит преподаватель")
class_table = "\n".join(f"| {k} {CLASSES[k]} | {', '.join(t for t in STUDENT_TICKERS if CLASS_OF[t] == k)} |"
                        for k in CLASSES)
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.metadata.update({"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python"}, "colab": {"name": "practice-04.ipynb"}})
cells = [
md(f'''# Практика 4. Отчётность компаний: RFSD
**Количественные финансы · НИУ ВШЭ · 26 ноября 2026**

Сегодня работаем с бухгалтерской отчётностью российских компаний из набора RFSD. Вопрос занятия: **что можно узнать об отрасли по открытой отчётности и насколько этим данным можно доверять?** На паре работаем с выборкой книги, дома – с полным RFSD: домашняя часть – начало проекта 1 «Фундаментальный анализ отрасли».

Материал – [глава 5 «Большие данные корпоративной отчётности»]({BOOK_URL}/05-accounting-data.html).

| Когда | Задания |
|---|---|
| Вторая пара · 60 минут | 0–5 |
| Дома: начало проекта 1 | 6–8 и всё, что не успели |

Сдаём выполненный ноутбук `practice04_фамилия.ipynb` с ответами в ячейках «**Ответ:**» {submit}.

Если застряли больше чем на 10 минут, запишите в ответ, что пробовали, текст ошибки и вопрос, и переходите к следующему заданию.

**Имя и группа:** …

**Моя акция:** …

**Мой класс ОКВЭД** (по таблице ниже): …

| Класс ОКВЭД | Акции из самостоятельной работы 2 ([таблица распределения]({SHEET_URL})) |
|---|---|
{class_table}'''),
md('''## 0. Подготовка
Ячейки ниже подключают библиотеки и загружают два файла: выборку RFSD из книги (8 МБ) и отчётность эмитентов акций курса. Выполните их один раз, редактировать не нужно. Без сети ноутбук читает файлы из папки `data` рядом с собой.

Нужна библиотека **Polars**. В Google Colab она уже установлена; в своём Jupyter выполните `pip install polars pyarrow`.'''),
code('''import numpy as np
import pandas as pd
import polars as pl
import matplotlib.pyplot as plt

plt.rcParams.update({"figure.figsize": (10, 4), "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False})
pd.options.display.float_format = "{:,.3f}".format
pl.Config.set_tbl_rows(20)
print("Библиотеки загружены, polars", pl.__version__)'''),
code(f'''# Загрузка данных: сначала с GitHub, без сети – из папки data рядом с ноутбуком.
import hashlib, io, urllib.request   # urllib – и для полного RFSD в задании 6
from pathlib import Path

def fetch(url, local, sha):
    local = Path(local)
    try:
        raw = urllib.request.urlopen(url, timeout=30).read()
        local.parent.mkdir(exist_ok=True)
        local.write_bytes(raw)                 # копия для Polars и для работы без сети
        print("Загружено с GitHub:", local.name)
    except OSError:
        raw = local.read_bytes()
        print("Нет доступа к GitHub, прочитан файл", local)
    assert hashlib.sha256(raw).hexdigest() == sha, f"{{local.name}} отличается от снимка занятия"
    return raw

SAMPLE = Path("data/rfsd_sample.parquet")
fetch("{SAMPLE_URL}", SAMPLE, "{sample_sha}")
raw = fetch("{ISSUERS_URL}", "data/{ISSUERS_CSV}", "{iss_sha}")

rfsd = pd.read_parquet(SAMPLE)                                     # pandas: вся таблица в памяти
issuers = pd.read_csv(io.BytesIO(raw), dtype={{"inn": str}})
print("Выборка:", rfsd.shape, "· годы", rfsd["year"].min(), "–", rfsd["year"].max())
print("Эмитенты:", issuers["ticker"].nunique(), "тикеров")''', metadata={"tags": ["setup"]}),
md(f'''### Что в данных
**Выборка книги** `rfsd_sample.parquet`: компании пяти классов ОКВЭД (10, 41, 47, 49, 62), выручка которых хотя бы в одном году 2018–{YEAR} превышала 1 млрд руб. Одна строка – отчёт компании за год. `name` – название, добавлено отдельно (в RFSD названий нет).

**Эмитенты** `{ISSUERS_CSV}`: отчётность головных компаний-эмитентов акций курса за 2018–{YEAR} гг. из полного RFSD. Пустые строки – отчётность не раскрыта или организации нет в RFSD.

Соглашения RFSD:
- денежные показатели – **в тысячах рублей**;
- строки, которые в формах пишутся в скобках (себестоимость, проценты к уплате), хранятся **отрицательными**;
- `filed = 1` – отчёт подан; `imputed = 1` – значения восстановлены; `outlier = 1` – подозрительный отчёт по оценке авторов RFSD.

Источник: RFSD (Bondarkov, Ledenev, Skougarevskiy, 2025), CC BY 4.0; снимок RFSD v3 от 02.09.2026.'''),
code('''TICKER = "..."       # ваша акция, например "GAZP"
MY_CLASS = "..."     # ваш класс ОКВЭД из таблицы в начале, например "47"
assert TICKER in set(issuers["ticker"]), "Такого тикера нет – проверьте написание"
assert MY_CLASS in ["10", "41", "47", "49", "62"], "Класс – две цифры из таблицы"
rfsd["div"] = rfsd["okved"].str[:2]
pos = lambda x: x.where(x > 0)          # знаменатель: только положительные значения
print(TICKER, "· класс", MY_CLASS)'''),
md(f'''## Задание 1. Эмитент вашей акции · 10 минут
1. За какие годы 2018–{YEAR} отчётность эмитента вашей акции раскрыта (`filed = 1`)? Какой у него код ОКВЭД?
2. Если за {YEAR} г. отчётности нет, объясните почему: банк или биржа (отчитываются перед Банком России), скрытая отчётность или другое. С какого года её не видно?
3. Если отчётность есть: выручка, доходы от участия (строка 2310) и чистая прибыль за последний раскрытый год в млрд руб. Это операционная компания или холдинг? По каким числам вы это видите?
4. Найдите в раскрытии эмитента выручку **группы** по МСФО за тот же год (сайт компании, раздел для инвесторов). Во сколько раз она отличается от выручки по РСБУ и почему? *(Можно дома.)*

**Ответ:** …'''),
code('''cols = ["year", "okved", "filed", "line_2110", "line_2310", "line_2400", "line_1300", "line_1600"]
me = issuers[issuers["ticker"] == TICKER]
print(me["issuer"].iloc[0], "· ИНН", me["inn"].iloc[0])
me[cols]
# Переведите тыс. руб. в млрд руб.: деление на 1e6
'''),
md(f'''## Задание 2. Единицы и знаки · 10 минут
АО «Тандер» (ИНН 2310031475) – операционная компания сети «Магнит».

**Сначала предскажите:** выручка «Тандера» за {YEAR} г. – это сотни миллиардов или триллионы рублей? Получила ли компания чистую прибыль?

1. Выручка, себестоимость, валовая прибыль (`line_2110 + line_2120`) и чистая прибыль «Тандера» за {YEAR} г. в млрд руб.
2. Чему была бы равна «валовая прибыль», если бы вы посчитали её как `line_2110 − line_2120`? Во сколько раз она завышена?
3. EBIT = `line_2300 − line_2330` и покрытие процентов = EBIT / (−`line_2330`). Как изменились проценты к уплате и покрытие с 2023 по {YEAR} г.? Что это говорит о долговой нагрузке компании?

**Предсказание:** …

**Ответ:** …'''),
code('''td = rfsd[rfsd["inn"] == "2310031475"].set_index("year")
td[["line_2110", "line_2120", "line_2300", "line_2330", "line_2400"]] / 1e6   # млрд руб.
# Посчитайте валовую прибыль, EBIT и покрытие процентов по годам
'''),
md(f'''## Задание 3. Parquet, CSV, pandas и Polars · 15 минут
1. Сохраните выборку в CSV (код ниже). Сравните размеры файлов CSV и parquet и время их чтения в pandas. Затем прочитайте из parquet только 5 столбцов (аргумент `columns=`). Во сколько раз это быстрее чтения всей таблицы?
2. Найдите ОАО «Молзавод „Гиагинский“» (ИНН `0101000776`) в таблице, прочитанной из CSV, и в таблице из parquet. Что не так с CSV и чем это опасно, когда таблицы соединяют по ИНН?
3. Постройте **ленивый** запрос Polars к `data/rfsd_sample.parquet`: поданные отчёты за {YEAR} г. вашего класса ОКВЭД, 10 крупнейших компаний по выручке (название, ИНН, код ОКВЭД, выручка и чистая прибыль в млрд руб.). Не забудьте `nulls_last=True`. Выведите план методом `.explain()`: на каком шаге применяется фильтр и сколько столбцов читается из файла?
4. Сколько компаний класса подали отчётность за {YEAR} г.? Какую долю выручки класса дают 10 крупнейших?

**Ответ:** …'''),
code('''import time
CSV = Path("data/rfsd_sample.csv")
rfsd.drop(columns="div").to_csv(CSV, index=False)
print(f"CSV: {CSV.stat().st_size / 1e6:.1f} МБ · parquet: {SAMPLE.stat().st_size / 1e6:.1f} МБ")

t = time.perf_counter(); from_csv = pd.read_csv(CSV, low_memory=False); t_csv = time.perf_counter() - t
t = time.perf_counter(); from_pq = pd.read_parquet(SAMPLE); t_pq = time.perf_counter() - t
print(f"Чтение в pandas: CSV {t_csv:.2f} с, parquet {t_pq:.2f} с")
# Допишите: чтение 5 столбцов из parquet; поиск ИНН "0101000776" в from_csv и from_pq; from_csv["inn"].dtype
'''),
code(f'''lf = pl.scan_parquet(SAMPLE)          # ничего не прочитано
q = (lf.filter((pl.col("year") == {YEAR}) & (pl.col("filed") == 1)
               & pl.col("okved").str.starts_with(MY_CLASS))
       .select("name", "inn", "okved", "line_2110", "line_2400"))
# Допишите: сортировка, head(10), столбцы в млрд руб.; затем q.explain() и q.collect()
'''),
md(f'''## Задание 4. Качество данных вашего класса · 15 минут
Для поданных отчётов вашего класса за {YEAR} г. посчитайте:

1. Долю отчётов, где не сходится баланс: |`line_1600` − `line_1700`| > 5 тыс. руб.
2. Долю отчётов с неположительным капиталом (`line_1300` ≤ 0).
3. Долю отчётов, где деньги в балансе (`line_1250`) и в отчёте о движении денежных средств (`line_4500`) расходятся больше чем на 5 тыс. руб. (среди отчётов, где есть обе строки).
4. Долю компаний класса, у которых основной код ОКВЭД менялся за 2018–{YEAR} гг.

Какая из проблем важнее всего для анализа рентабельности в вашем классе и почему?

**Ответ:** …'''),
code(f'''d = rfsd[(rfsd["year"] == {YEAR}) & (rfsd["filed"] == 1) & (rfsd["div"] == MY_CLASS)].copy()
print("Отчётов:", len(d))
mismatch = (d["line_1600"] - d["line_1700"]).abs() > 5
print(f"Баланс не сходится: {{mismatch.mean():.2%}}")
# Допишите остальные проверки
'''),
md(f'''## Задание 5. Коэффициенты: медиана и среднее · 15 минут
**Сначала предскажите:** средняя ROE в вашем классе выше или ниже медианной? Во сколько раз?

1. Посчитайте для всех пяти классов за {YEAR} г.: ROS, ROA, ROE, оборачиваемость активов, текущую ликвидность (формулы – на слайде и в таблице главы 5). Знаменатель – только положительный: функция `pos`.
2. Таблица медиан по классам. Где ваш класс выше остальных, где ниже? Объясните хотя бы одно различие бизнес-моделью.
3. Для своего класса: медиана, квартили (0,25 и 0,75) и среднее ROE. Почему среднее так далеко от медианы? Найдите компанию с наибольшей ROE и объясните, откуда такое значение.

**Предсказание:** …

**Ответ:** …'''),
code(f'''a = rfsd[(rfsd["year"] == {YEAR}) & (rfsd["filed"] == 1)].copy()
a["ros"] = a["line_2400"] / pos(a["line_2110"])
a["roe"] = a["line_2400"] / pos(a["line_1300"])
# Допишите roa, turnover, current; затем a.groupby("div")[[...]].median()
'''),
md(f'''## Задание 6. Проект 1: кандидаты в тему по полному RFSD · дома, 40 минут
Выборка книги – только пять классов и компании с выручкой от 1 млрд руб. Для проекта нужен полный RFSD. Это задание – первый шаг проекта 1: вы проверяете, хватает ли данных для темы.

Выберите **2–3 кандидата**: отрасль (код ОКВЭД любого уровня, например `10.51` – молочная продукция) или отрасль в одном регионе. Коды удобно искать в [классификаторе rustata](https://rustata.ru/classifier/okved2).

Для каждого кандидата за {YEAR} г. (поданные отчёты):

1. Сколько компаний и сколько из них с выручкой от 100 млн руб.? Суммарная выручка, доля 5 крупнейших.
2. **Охват:** сравните суммарную выручку в RFSD с выручкой организаций по данным Росстата для того же кода (страница кода в классификаторе rustata). Какую часть отрасли вы видите?
3. **Скрытые лидеры:** назовите 2–3 крупнейшие компании отрасли, которые вы знаете (сайты компаний, рейтинги, новости), найдите их ИНН и проверьте, есть ли их отчёт за {YEAR} г.
4. Какой кандидат проходит правило проекта (не меньше 30 компаний с выручкой от 100 млн руб.) и в каком данных больше? Сохраните таблицу выбранной темы в parquet.

**Ответ:** …'''),
md(f'''### Два способа читать полный RFSD
Файл RFSD за {YEAR} г. – {FULL["mb"]} МБ, {fmt(FULL["rows"], 2)} млн строк и {FULL["cols"]} столбца.

- **Б. Скачать файл один раз** (`USE_DOWNLOAD = True`, по умолчанию). Скачивание занимает 1–3 минуты, потом запросы быстрые и не требуют сети. В Colab файл пропадает после закрытия сессии – скачайте заново или сохраните на Google Drive.
- **А. Читать прямо с Hugging Face** (`USE_DOWNLOAD = False`). Polars скачивает только нужные столбцы, но при каждом запуске заново.

Ссылка закреплена на версию RFSD, с которой работает курс: ответы не изменятся, если авторы обновят набор.

**Если Hugging Face не открывается из вашей сети** (так бывает в российских сетях), выполните это задание в Google Colab: он работает на серверах Google.

В полном RFSD **нет названий компаний**: ищите их по ИНН в [ГИР БО](https://bo.nalog.gov.ru). Нет и столбца `year`: год – в имени файла. Регионы записаны латиницей: `moscow city`, `moscow reg.`, `tatarstan`….'''),
code(f'''RFSD_REV = "{HF_REV}"                    # версия RFSD v3
PART = f"RFSD/year={YEAR}/part-0.parquet"
USE_DOWNLOAD = True                                 # False – читать прямо с Hugging Face

if USE_DOWNLOAD:
    source = Path(f"data/rfsd_{YEAR}.parquet")
    if not source.exists():
        import shutil
        source.parent.mkdir(exist_ok=True)
        tmp = source.with_suffix(".part")
        print("Скачиваю", PART, "– 1–3 минуты…")
        try:
            url = f"https://huggingface.co/datasets/irlspbru/RFSD/resolve/{{RFSD_REV}}/{{PART}}"
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as out:
                shutil.copyfileobj(r, out, 1 << 20)
        except OSError as e:
            raise RuntimeError("Hugging Face не отвечает из вашей сети. Откройте ноутбук в Google Colab "
                               "или скачайте файл по ссылке выше в браузере и положите в data/") from e
        tmp.rename(source)                          # недокачанный файл не останется под рабочим именем
    print(f"{{source}}: {{source.stat().st_size / 1e6:.0f}} МБ")
else:
    source = f"hf://datasets/irlspbru/RFSD@{{RFSD_REV}}/{{PART}}"

full = pl.scan_parquet(source)
print(len(full.collect_schema()), "столбцов")'''),
code('''COLS = ["inn", "okved", "region", "line_2110", "line_2120", "line_2200", "line_2300", "line_2330",
        "line_2400", "line_1300", "line_1600", "line_1410", "line_1510"]

def candidate(okved, region=None):
    """Поданные отчёты по коду ОКВЭД (и региону) – таблица Polars."""
    cond = (pl.col("filed") == 1) & pl.col("okved").str.starts_with(okved)
    if region:
        cond = cond & (pl.col("region") == region)
    return full.filter(cond).select(COLS).collect()

def summary(df):
    rev = df["line_2110"].fill_null(0).sort(descending=True)
    return {"компаний": df.height,
            "от 100 млн руб.": int((rev >= 100_000).sum()),
            "выручка, млрд руб.": round(rev.sum() / 1e6, 1),
            "доля топ-5": round(rev.head(5).sum() / rev.sum(), 3) if rev.sum() > 0 else None}

# Ваши кандидаты: название -> (код ОКВЭД, регион или None)
CANDIDATES = {"Молочная продукция": ("10.51", None),
              "...": ("...", None)}
tables = {name: candidate(*args) for name, args in CANDIDATES.items()}
pd.DataFrame.from_dict({name: summary(df) for name, df in tables.items()}, orient="index")'''),
code('''# Регионы в RFSD: full.select("region").unique().sort("region").collect()
# 5 крупнейших компаний кандидата:
# tables["Молочная продукция"].sort("line_2110", descending=True, nulls_last=True).head(5)

# Скрытые лидеры: впишите ИНН известных компаний отрасли
LEADERS = ["..."]
full.filter(pl.col("inn").is_in(LEADERS)).select("inn", "okved", "region", "filed", "line_2110").collect()

# Таблица выбранной темы – для проекта:
# tables["..."].write_parquet("data/project1.parquet")
'''),
md('''## Задание 7. Проверка кода ИИ-ассистента · дома, 10 минут
Ассистента попросили «посчитать по классам ОКВЭД валовую прибыль, ROE и отношение долга к EBITDA». Код ниже работает без ошибок, но результат неверен.

Найдите не меньше четырёх ошибок, объясните каждую и напишите исправленный код. Сравните результаты до и после.

**Ответ:** …'''),
code(f'''# Код ассистента – не меняйте эту ячейку, исправленный вариант напишите ниже
x = rfsd[rfsd["year"] == {YEAR}].copy()
x["gross"] = x["line_2110"] - x["line_2120"]
x["ebitda"] = x["line_2300"] + x["line_2330"]
x["roe"] = x["line_2400"] / x["line_1300"]
x["debt_to_ebitda"] = (x["line_1410"] + x["line_1510"]) / x["ebitda"]
print(x.groupby(x["okved"].str[:2])[["gross", "roe", "debt_to_ebitda"]].mean())'''),
code('''# Исправленный код
'''),
md('''## Задание 8. Заявка на проект 1 · дома, 150–250 слов
Это заявка на тему проекта 1. Тему также впишите в таблицу курса: темы не повторяются, преподаватель подтверждает заявку.

1. **Тема** и **правило отбора компаний**: коды ОКВЭД, регион, год, порог выручки, `filed = 1`.
2. **Почему эта тема:** число компаний, доля пяти крупнейших, охват по Росстату и скрытые лидеры – ваши числа из задания 6. Почему не другие кандидаты?
3. **Гипотеза** к вопросу проекта «за счёт чего лидеры отрасли эффективнее остальных – маржи, оборачиваемости или долговой нагрузки?». Запишите её **до** расчётов и объясните, на чём она основана.
4. Два главных **ограничения данных** для вашей темы и как каждое может сдвинуть вывод.

Если пользовались ИИ, запишите: **что спросили**, **что получили**, **как проверили**.

**Заявка:** …

**Журнал ИИ:** …'''),
md(f'''## Перед сдачей
- Перезапустите ядро и выполните все ячейки сверху вниз.
- Проверьте, что в каждом задании заполнена ячейка «**Ответ:**».
- Сохраните файл `practice04_фамилия.ipynb` и сдайте его {submit}.

Справочник строк отчётности – `rfsd_lines.csv` в [данных книги](https://github.com/quantviews/quant-finance-book/tree/main/data); синтаксис Polars – в [главе 5]({BOOK_URL}/05-accounting-data.html#sec-polars).'''),
]
nb.cells = cells
nbf.validate(nb)
nbf.write(nb, HERE / "practice-04.ipynb")
print(f"Эмитенты: {len(iss)} строк, SHA256 {iss_sha}")
print(f"Ноутбук: {len(cells)} ячеек; слайды: _lecture.qmd; графики: figures/")
print(json.dumps(dict(open_=open_, hidden=hidden_since, absent=absent, banks=banks, okved_change=okved_change,
                      med=med.round(3).to_dict(), neg_eq=neg_eq, mism=mism, cash=cash_match,
                      hid=[int(hid.loc[YEAR, "hidden"]), int(hid.loc[YEAR, "large"]), hid_share, hid_rev],
                      cov=[coverage.loc[2018], coverage.loc[YEAR]], fa=fa.round(3).to_dict(),
                      roe=[roe.median(), roe.mean(), *roe_q.tolist()], aflt=[aflt["line_2400"], aflt["line_1300"]],
                      class_of=CLASS_OF), default=str, ensure_ascii=False))

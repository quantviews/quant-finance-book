"""Слайды блока «Финансовые данные» занятия 3 (вместо лекции 2): _data.qmd и графики.

Запуск из корня книги ПОСЛЕ build_materials.py:
    python lessons/03-returns-risk/build_data_slides.py
Источники: CSV занятия (data/prices_2015_2026.csv), макроданные из rustata
(data/cpi-source.parquet, data/usdrub-source.parquet; выгрузка – export_macro.py),
RUONIA (data/ruonia-source.parquet) и снимок книги (data/stocks_raw.parquet, qf.data).
Числа на слайдах не вписаны вручную.
"""
from pathlib import Path
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
BOOK = HERE.parents[1]
sys.path.insert(0, str(BOOK))
from qf import data as book_data  # noqa: E402

BLUE, ORANGE, GREEN, RED, GREY = "#34699A", "#C8702A", "#3F8F5B", "#B8412E", "#64748B"
font_dir = BOOK / "fonts" / "ibm-plex-sans"
for filename in ["IBMPlexSans-Regular.ttf", "IBMPlexSans-SemiBold.ttf"]:
    font_manager.fontManager.addfont(str(font_dir / filename))
plt.rcParams.update({"font.family": "IBM Plex Sans", "font.size": 15,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.spines.bottom": False,
                     "axes.grid": True, "grid.color": "#D6DDE6", "grid.alpha": .65,
                     "axes.axisbelow": True, "svg.fonttype": "path", "axes.unicode_minus": False})

fmt = lambda x, d=1: f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")
pct = lambda x, d=1: fmt(100 * x, d) + "%"
dt = lambda d: pd.Timestamp(d).strftime("%d.%m.%Y")
MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь",
          "октябрь", "ноябрь", "декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
              "октября", "ноября", "декабря"]
month_label = lambda d: f"{MONTHS[pd.Timestamp(d).month - 1]} {pd.Timestamp(d).year} г."


def finish(fig, ax, name, pctfmt=False):
    if pctfmt:
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{100 * y:.0f}%".replace("-", "−")))
    fig.savefig(HERE / "figures" / name)
    plt.close(fig)


# ---------------------------------------------------------------- данные
df = pd.read_csv(HERE / "data" / "prices_2015_2026.csv", parse_dates=["date"]).set_index("date")
meta = json.loads((HERE / "data" / "metadata.json").read_text(encoding="utf-8"))
src = json.loads((HERE / "data" / "source.json").read_text(encoding="utf-8"))
macro = json.loads((HERE / "data" / "macro-source.json").read_text(encoding="utf-8"))
cpi = pd.read_parquet(HERE / "data" / "cpi-source.parquet").set_index("period")["cpi_mom"] / 100
usd = pd.read_parquet(HERE / "data" / "usdrub-source.parquet").set_index("period")["usdrub"]
ruonia = pd.read_parquet(HERE / "data" / "ruonia-source.parquet")
ruonia = ruonia.assign(date=pd.to_datetime(ruonia["date"])).set_index("date")["rate"] / 100

# Ловушка постраничной выдачи: торговых дней в 2023 г. в календаре занятия.
days_2023 = int((df.index.year == 2023).sum())

# Паспорт ряда SBER в снимке занятия.
sber = df["SBER"]
p = sber.dropna()
inside = sber.loc[p.index[0]:p.index[-1]]
gaps = p.index.to_series().diff().dt.days
passport = dict(first=dt(p.index[0]), last=dt(p.index[-1]), n=len(p), missing=int(inside.isna().sum()),
                gap=int(gaps.max()), gap_from=dt(p.index[p.index.get_loc(gaps.idxmax()) - 1]),
                gap_to=dt(gaps.idxmax()), exported=dt(src["exported"]))

# Консолидация ВТБ: сырые цены ISS из снимка книги.
raw = book_data.load_stocks_raw(["VTBR"]).assign(date=lambda d: pd.to_datetime(d["date"]))
vtb = raw.set_index("date")["close"].loc["2024-01-01":"2024-12-31"]
splits = book_data.load_reference("splits")
sp = splits[splits["ticker"] == "VTBR"].iloc[0]
sp_date, ratio = pd.Timestamp(sp["date"]), float(sp["ratio"])
before, after = vtb.loc[:sp_date - pd.Timedelta(days=1)], vtb.loc[sp_date:]
vtb_adj = pd.concat([before / ratio, after])
raw_jump = after.iloc[0] / before.iloc[-1]
adj_jump = after.iloc[0] / (before.iloc[-1] / ratio) - 1
imoex_days = df.index[(df.index > before.index[-1]) & (df.index < sp_date)]
vtb_info = dict(last=dt(before.index[-1]), last_px=fmt(before.iloc[-1], 5), first=dt(sp_date),
                first_px=fmt(after.iloc[0], 2), k=fmt(1 / ratio, 0), raw=fmt(raw_jump, 0),
                adj_px=fmt(before.iloc[-1] / ratio, 2), adj=pct(adj_jump), pause=len(imoex_days))

# Ошибка выжившего: тот же расчёт, что в главе 3 книги.
prices = book_data.load_prices(start="2015-12-30", end="2025-12-31")
last_date = prices.apply(lambda c: c.last_valid_index())
survivor = last_date >= pd.Timestamp("2025-12-01")
rows = []
for year in range(2016, 2026):
    start = prices.loc[:f"{year - 1}-12-31"].iloc[-1]
    end = prices.loc[str(year)].apply(lambda c: c.dropna().iloc[-1] if c.notna().any() else np.nan)
    r = (end / start - 1).dropna()
    rows.append({"all": r.mean(), "surv": r[survivor[r.index]].mean()})
surv = pd.DataFrame(rows)
surv_info = dict(all=pct(surv["all"].mean()), surv=pct(surv["surv"].mean()),
                 bias=fmt(100 * (surv["surv"] - surv["all"]).mean(), 1),
                 dead=int((~survivor).sum()), total=int(prices.shape[1]))
pikk_last = dt(df["PIKK"].last_valid_index())

# Переименования из справочника книги.
renames = book_data.load_reference("renames").sort_values("date")
rename_rows = "\n".join(f"| {r.old} → {r.new} | {dt(r.date)} |" for r in renames.tail(4).itertuples())

# Инфляция: месячный ИПЦ -> уровень цен -> год к году.
cpi_level = cpi.cumprod()
cpi_yoy = (cpi_level / cpi_level.shift(12) - 1).dropna()
cpi_yoy = cpi_yoy.loc["2016-01-01":]
cpi_last = cpi.index[-1]
infl_peak = (cpi_yoy.idxmax(), cpi_yoy.max())
ruonia_m = ruonia.resample("MS").mean().reindex(cpi_yoy.index)
real_rate = (1 + ruonia_m) / (1 + cpi_yoy) - 1
neg_months = real_rate[real_rate < 0]
# Эпизоды отрицательной реальной ставки: подряд идущие месяцы.
runs = (real_rate >= 0).cumsum()[real_rate < 0]
mm = lambda d: d.strftime("%m.%Y")
episodes = [(g.index[0], g.index[-1]) for _, g in runs.groupby(runs)]
neg_text = ", ".join(mm(a) if a == b else f"{mm(a)}–{mm(b)}" for a, b in episodes)

# Номинальная, реальная и долларовая доходность: с начала снимка до конца последнего месяца с ИПЦ.
end_m = cpi_last + pd.offsets.MonthEnd(0)
s = df.loc[:end_m]
years = (s.index[-1] - s.index[0]).days / 365.25
infl_total = float(cpi.loc[s.index[0].strftime("%Y-%m"):cpi_last].prod())
infl_ann = infl_total ** (1 / years) - 1
usd_d = usd.reindex(s.index, method="ffill")
real_rows, real = [], {}
for name, label in [("IMOEX", "IMOEX – только цены"), ("MCFTR", "MCFTR – с дивидендами"),
                    ("RUONIA", "Денежный рынок (RUONIA)")]:
    x = s[name].dropna()
    g = x.iloc[-1] / x.iloc[0]
    nom = g ** (1 / years) - 1
    rea = (g / infl_total) ** (1 / years) - 1
    xu = (x / usd_d.reindex(x.index)).dropna()
    usd_r = (xu.iloc[-1] / xu.iloc[0]) ** (1 / years) - 1
    real[name] = dict(nom=nom, real=rea, usd=usd_r)
    real_rows.append(f"| {label} | {pct(nom)} | {pct(rea)} | {pct(usd_r)} |")
real_rows = "\n".join(real_rows)
usd_info = dict(start=fmt(usd_d.iloc[0], 2), end=fmt(usd_d.iloc[-1], 2),
                max_d=dt(usd.loc["2022"].idxmax()), max=fmt(usd.loc["2022"].max(), 2))
real_period = f"{dt(s.index[0])}–{dt(s.index[-1])}"
cat = macro["catalog"]

# MCFTR в рублях и в ценах начала периода: 100 = первый день снимка, ИПЦ накоплен помесячно с января 2015 г.
m_nom = s["MCFTR"].dropna().resample("ME").last()
m_nom = pd.concat([pd.Series({s.index[0]: s["MCFTR"].dropna().iloc[0]}), m_nom]) / s["MCFTR"].dropna().iloc[0] * 100
price_idx = cpi.loc[s.index[0].strftime("%Y-%m"):cpi_last].cumprod()
price_idx.index = price_idx.index + pd.offsets.MonthEnd(0)
price_idx = pd.concat([pd.Series({s.index[0]: 1.0}), price_idx]) * 100
m_real = m_nom / price_idx * 100
real_peak = m_real.loc[:"2022-12-31"].idxmax()
real_trough = m_real.loc[real_peak:].idxmin()
real_info = dict(nom=fmt(m_nom.iloc[-1], 0), prices=fmt(price_idx.iloc[-1], 0), real=fmt(m_real.iloc[-1], 0),
                 peak=fmt(m_real[real_peak], 0), peak_m=mm(real_peak), trough=fmt(m_real[real_trough], 0),
                 trough_m=mm(real_trough), fall=pct(1 - m_real[real_trough] / m_real[real_peak], 0),
                 below=pct(1 - m_real.iloc[-1] / m_real[real_peak], 0))
assert abs(m_nom.iloc[-1] / 100 - s["MCFTR"].dropna().iloc[-1] / s["MCFTR"].dropna().iloc[0]) < 1e-9
assert abs(price_idx.iloc[-1] / 100 - infl_total) < 1e-9

# ---------------------------------------------------------------- графики
fig, ax = plt.subplots(figsize=(11.8, 4.4), layout="constrained")
ax.plot(before.index, before, color=GREY, lw=1.6, label="Сырые цены ISS")
ax.plot(vtb_adj.index, vtb_adj, color=BLUE, lw=2.2, label=f"С поправкой на консолидацию {vtb_info['k']}:1")
ax.plot(after.index, after, color=GREY, lw=1.6)
ax.axvline(sp_date, color=RED, lw=1, ls="--")
ax.set_yscale("log")
ax.set_yticks([0.01, 0.1, 1, 10, 100], labels=["0,01", "0,1", "1", "10", "100"])
ax.minorticks_off()
ax.set_ylabel("руб., лог. шкала")
ax.set_xlim(vtb.index[0], vtb.index[-1])
ticks = pd.date_range("2024-01-01", "2024-12-01", freq="MS")
ax.set_xticks(ticks, labels=[MONTHS[t.month - 1][:3] for t in ticks])
ax.legend(frameon=False, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.01))
finish(fig, ax, "vtbr.svg")

fig, ax = plt.subplots(figsize=(11.8, 4.4), layout="constrained")
ax.plot(cpi_yoy.index, cpi_yoy, color=RED, lw=2.2, label="Инфляция: ИПЦ к тому же месяцу прошлого года")
ax.plot(ruonia_m.index, ruonia_m, color=GREEN, lw=2.2, label="RUONIA, среднее за месяц")
ax.fill_between(cpi_yoy.index, ruonia_m, cpi_yoy, where=ruonia_m < cpi_yoy, color=RED, alpha=.15,
                interpolate=True)
ax.set_xlim(cpi_yoy.index[0], cpi_yoy.index[-1])
ax.set_ylim(0, None)
ax.legend(frameon=False, ncol=2, loc="lower left", bbox_to_anchor=(0, 1.01), fontsize=13)
finish(fig, ax, "inflation.svg", pctfmt=True)

fig, ax = plt.subplots(figsize=(11.8, 4.4), layout="constrained")
for ser, color, label in [(m_nom, BLUE, "MCFTR в рублях"), (price_idx, RED, "Цены: накопленный ИПЦ"),
                          (m_real, ORANGE, "MCFTR в реальном выражении")]:
    ax.plot(ser.index, ser, color=color, lw=2.2, label=label)
    ax.annotate(fmt(ser.iloc[-1], 0), (ser.index[-1], ser.iloc[-1]), xytext=(6, 0), textcoords="offset points",
                va="center", color=color, fontsize=13, weight="semibold")
ax.axhline(100, color=GREY, lw=.8)
ax.set_xlim(m_nom.index[0], m_nom.index[-1] + pd.Timedelta(days=200))
ax.set_ylabel("январь 2015 г. = 100")
ax.legend(frameon=False, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.01), fontsize=13)
finish(fig, ax, "mcftr-real.svg")

# ---------------------------------------------------------------- слайды
slides = f'''## Финансовые данные: четыре группы

| Группа | Примеры | Частота | Когда становится известно |
|---|---|---|---|
| Рыночные | цены сделок, объёмы, котировки | от микросекунд до дня | сразу после торгов |
| Фундаментальные | выручка, прибыль, долг, дивиденды | квартал, год | через месяцы: отчётность за 2025 г. – весной 2026 г. |
| Макроэкономические и ставки | ключевая ставка, RUONIA, инфляция, курс рубля | день, месяц, квартал | ставки и курс – сразу, инфляция – в следующем месяце |
| Альтернативные | новости, поисковые запросы, платежи | разная | разная |

::: {{.prompt}}
В таблице число записано под датой периода, к которому оно относится. Когда о нём узнал инвестор?
:::

## Где брать данные по российскому рынку

| Что нужно | Источник | Доступ |
|---|---|---|
| Торги акциями, облигациями, индексы | Московская биржа: ISS, iss.moex.com | бесплатно, без ключа |
| Ключевая ставка, RUONIA, курсы валют | Банк России, cbr.ru | бесплатно |
| Инфляция, производство, доходы, регионы, бюджет | Росстат, ЕМИСС, Казначейство → **rustata.ru** | бесплатная регистрация, токен |
| Отчётность компаний | e-disclosure.ru, bo.nalog.ru, набор RFSD | бесплатно |
| Дивиденды, сплиты, переименования | сообщения эмитентов и биржи | собирать и проверять самим |
| Зарубежные рынки и макро | FRED, SEC EDGAR, Yahoo Finance | бесплатно; по российским бумагам после 2022 г. ненадёжно |

::: {{.source}}
Глава 2 книги: разделы «Московская биржа и ISS», «Данные Банка России», «Российская экономическая статистика: rustata».
:::

## Как устроена Московская биржа

::: {{.columns}}
::: {{.column width="44%"}}
**Рынки:** фондовый (акции, облигации, фонды), валютный, денежный (РЕПО), срочный.

**Режимы торгов** (boards): одна акция торгуется в нескольких. Основной для акций – **TQBR**: там большая часть оборота, по нему считаются индексы.

Неполные лоты, крупные пакеты, РЕПО – другие цены. Режимы не смешиваем.
:::
::: {{.column width="52%"}}
Адрес запроса повторяет иерархию биржи:

```text
iss.moex.com/iss/history/engines/stock
  /markets/shares/boards/TQBR
  /securities/SBER.json
  ?from=2023-01-01&till=2023-12-31
```

движок `stock` → рынок `shares` → режим `TQBR` → бумага `SBER`

Ответ – набор таблиц: у каждой список столбцов `columns` и строки `data`.
:::
:::

## Ловушка постраничной выдачи

::: {{.columns}}
::: {{.column width="46%"}}
В 2023 г. было **{days_2023}** торговых дней. Первый запрос за год возвращает **100** строк.

Таблица `history.cursor`: `INDEX` – первая строка страницы, `TOTAL` – всего строк, `PAGESIZE` – размер страницы.

Код работает без ошибок, данные выглядят правдоподобно, но это первые 100 дней.
:::
::: {{.column width="50%"}}
```python
period = {{"from": "2023-01-01", "till": "2023-12-31"}}
pages, first = [], 0
while True:
    resp = iss_get(path, **period, start=first)
    pages.append(resp["history"])
    total = resp["history.cursor"]["TOTAL"][0]
    first += len(resp["history"])
    if len(resp["history"]) == 0 or first >= total:
        break
hist = pd.concat(pages, ignore_index=True)
```
:::
:::

::: {{.prompt}}
Проверка: около 250 строк в год, даты не повторяются. С этого стоит начинать проверку кода, написанного ИИ-ассистентом.
:::

## Паспорт данных

Без паспорта результат нельзя воспроизвести: биржа уточняет историю, выходят новые дивиденды. Пример – SBER в снимке занятия.

| Поле | SBER |
|---|---|
| Источник и режим | ISS Московской биржи, TQBR; дивиденды – закрытияреестров.рф |
| Дата выгрузки | {passport["exported"]} |
| Первая и последняя дата | {passport["first"]} – {passport["last"]} |
| Дней с ценой · пропусков внутри ряда | {fmt(passport["n"], 0)} · {passport["missing"]} |
| Самый длинный разрыв | {passport["gap"]} дн.: {passport["gap_from"]} – {passport["gap_to"]} |
| Поправки | `adj_close` – сплиты и дивиденды, `close` – только сплиты |

::: {{.prompt}}
Самый длинный разрыв приходится на остановку торгов в 2022 г. Что сделать с доходностью через этот разрыв?
:::

## Консолидация: ВТБ, июль 2024 г.

![](figures/vtbr.svg){{.chart}}

::: {{.small}}
Последняя цена до события – {vtb_info["last_px"]} руб. ({vtb_info["last"]}), первая после – {vtb_info["first_px"]} руб. ({vtb_info["first"]}): по сырым ценам рост в {vtb_info["raw"]} раз. С поправкой {vtb_info["k"]}:1 – {vtb_info["adj_px"]} руб. и {vtb_info["adj"]}. Между датами {vtb_info["pause"]} торговых дня бумага не торговалась.
:::

## Дивиденды: экс-дивидендная дата

::: {{.columns}}
::: {{.column width="50%"}}
**Дата закрытия реестра** – кто в реестре, тот получит дивиденд.

**Экс-дивидендная дата** – первый день торгов без права на дивиденд: цена открывается ниже примерно на дивиденд.

- T+1 (с 31.07.2023): экс-дата = дата закрытия реестра.
- T+2 (раньше): экс-дата – торговый день перед закрытием реестра.
:::
::: {{.column width="46%"}}
**Корректировка прошлых цен**

k = 1 − D / P<sub>t−1</sub>

D – дивиденд, P<sub>t−1</sub> – закрытие накануне экс-даты. Все цены до экс-даты умножаются на k.

SBER, реестр 18.07.2025, дивиденд 34,84 руб.: по `close` – падение, по `adj_close` – обычный день.
:::
:::

::: {{.prompt}}
Скорректированные цены прошлых лет меняются после каждой новой выплаты. Что это значит для сохранённой выгрузки?
:::

## Переименования и ошибка выжившего

::: {{.columns}}
::: {{.column width="40%"}}
**Одна компания – несколько тикеров**

| Тикер | С даты |
|---|---|
{rename_rows}

Поиск по новому тикеру теряет историю до переименования.
:::
::: {{.column width="56%"}}
**Ошибка выжившего:** выбираем акции по сегодняшнему списку и теряем ушедшие с биржи.

В данных книги за 2016–2025 гг. средняя годовая доходность по всем бумагам – {surv_info["all"]}, только по «выжившим» – {surv_info["surv"]}: **+{surv_info["bias"]} п.п. в год**. Ушли {surv_info["dead"]} бумаг из {surv_info["total"]}.

В снимке занятия у PIKK последняя цена – {pikk_last}. Если бумагу снимут с торгов, выборка «по сегодняшнему списку» её потеряет.
:::
:::

## Проверка качества: что смотреть всегда

1. **Полнота:** число строк по годам, повторяющиеся даты, сверка с календарём индекса.
2. **Режим и источник:** TQBR, одна и та же бумага во всём периоде, учтены переименования.
3. **Скачки больше 30–50% за день:** сплит без поправки – ошибка, 24.02.2022 – реальное событие.
4. **Дивиденды:** какой столбец – `close` или `adj_close`.
5. **Пропуски:** дни без сделок и остановки торгов не заполняются нулевой доходностью.
6. **Момент доступности:** не использовать число раньше, чем о нём узнали.

::: {{.prompt}}
Выбросы не удаляем по порогу: вместе с ними из данных исчезают кризисы, то есть сам риск.
:::

## Макроданные: зачем они инвестору

::: {{.columns}}
::: {{.column width="32%"}}
### Инфляция

Номинальный рост денег ничего не говорит о покупательной способности.

**Реальная доходность:** (1 + R) / (1 + π) − 1
:::
::: {{.column width="32%"}}
### Курс рубля

Для инвестора, который считает в долларах или покупает импорт, результат другой.

Доходность в долларах: R<sub>руб</sub> с поправкой на изменение курса.
:::
::: {{.column width="32%"}}
### Ставки

Безрисковая альтернатива акциям: ключевая ставка, RUONIA.

От неё считаем премию за риск и коэффициент Шарпа.
:::
:::

::: {{.prompt}}
Где взять инфляцию за 10 лет одним рядом, с датой публикации каждого значения?
:::

## rustata: российская статистика в одном месте

::: {{.columns}}
::: {{.column width="50%"}}
**rustata.ru** – проект автора курса.

- {cat["datasets"]} наборов: Росстат, Банк России, Казначейство, ФНС; более {fmt(cat["series"] / 1e6, 0)} млн рядов.
- Единые справочники территорий, товаров и единиц.
- **История публикаций:** дата, когда значение стало известно (`as_of`).
- Сайт: поиск словами, графики, регионы, CSV.
- API по токену, регистрация бесплатная: rustata.ru/api.
:::
::: {{.column width="46%"}}
**Чем неудобны первоисточники**

- Данные разбросаны по ЕМИСС (fedstat.ru) и бюллетеням Excel.
- Показатели – номера вроде «31074», названия рядов меняются от выгрузки к выгрузке.
- Статистика пересматривается: в свежей выгрузке – исправленное значение, а не известное в момент публикации.
:::
:::

## Инфляция и денежный рынок

![](figures/inflation.svg){{.chart}}

::: {{.small}}
Пик инфляции – {pct(infl_peak[1])} ({month_label(infl_peak[0])}). Заливка – месяцы, когда RUONIA была ниже инфляции: реальная ставка денежного рынка отрицательна ({neg_text}).
:::

::: {{.source}}
ИПЦ – Росстат (ЕМИСС, показатель 31074), через rustata.ru; RUONIA – Банк России. Последний месяц ИПЦ – {MONTHS[cpi_last.month - 1]} {cpi_last.year}.
:::

## Рубли и покупательная способность

![](figures/mcftr-real.svg){{.chart}}

::: {{.small}}
Реальный индекс = MCFTR в рублях / накопленный ИПЦ × 100 – сколько товаров и услуг можно купить на вложение. Реальный пик – {real_info["peak"]} ({real_info["peak_m"]}), дно – {real_info["trough"]} ({real_info["trough_m"]}), падение на {real_info["fall"]}; в конце периода – на {real_info["below"]} ниже пика.
:::

::: {{.source}}
MCFTR – Московская биржа, на конец месяца; ИПЦ – Росстат через rustata.ru. {real_period}. До налогов и издержек.
:::

## Номинальная, реальная и долларовая доходность

{real_period}, среднегодовой рост (CAGR)

| | Номинальная, руб. | Реальная, с поправкой на инфляцию | В долларах |
|---|---|---|---|
{real_rows}

::: {{.small}}
Период заканчивается последним месяцем с данными по инфляции, поэтому номинальные числа немного отличаются от слайдов дальше. Цены за период выросли в {fmt(infl_total, 2)} раза ({pct(infl_ann)} в год). Курс доллара Банка России: {usd_info["start"]} руб. в начале периода, {usd_info["end"]} руб. в конце, максимум – {usd_info["max"]} руб. ({usd_info["max_d"]}).
:::

::: {{.prompt}}
Ценовой индекс IMOEX в реальном выражении отрицателен. Что это говорит о роли дивидендов?
:::

## Инфляция из rustata: код

```python
import io, requests, pandas as pd
from qf import secrets                       # токен из файла .env, не из кода

API = "https://rustata.ru/api/v1"
headers = {{"Authorization": f"Bearer {{secrets.get('RUSTATA_TOKEN')}}"}}
resp = requests.get(f"{{API}}/data", headers=headers, timeout=60, params={{
    "dataset": "fedstat/indicator_31074",    # индексы потребительских цен
    "geo": "country", "class": "1",          # Россия, все товары и услуги
    "measure": "MOM", "start": "2015-01",    # к предыдущему месяцу
    "format": "csv"}})
cpi = pd.read_csv(io.StringIO(resp.text), sep=";", parse_dates=["period"])
price_level = (cpi.set_index("period")["value"] / 100).cumprod()
```

::: {{.small}}
Код продукта («1» – все товары и услуги) берётся из справочника набора `/reference/codes`, а не по памяти: в другом наборе тот же код означает другое. Токен – это пароль: его нельзя писать в код, который попадёт в отчёт или репозиторий.
:::

## Когда число стало известно

::: {{.columns}}
::: {{.column width="48%"}}
**Дата периода и дата публикации – разные даты.**

- ИПЦ за месяц публикуется в следующем месяце и не пересматривается.
- Промышленное производство, ВВП, бюджет уточняются после первой публикации.
- Отчётность компаний выходит через месяцы после конца года.
:::
::: {{.column width="48%"}}
**Заглядывание в будущее** – использовать на дату t то, что стало известно позже.

rustata хранит дату публикации каждого значения: параметр `as_of` возвращает ряд в том виде, в каком его знали на эту дату.
:::
:::

::: {{.prompt}}
Модель прогнозирует доходность акций по инфляции за тот же месяц. Почему её результат на истории будет лучше, чем в реальной работе?
:::
'''
(HERE / "_data.qmd").write_text(slides, encoding="utf-8")
print(json.dumps(dict(days_2023=days_2023, passport=passport, vtb=vtb_info, surv=surv_info, pikk=pikk_last,
                      infl_peak=[str(infl_peak[0].date()), infl_peak[1]], neg_text=neg_text,
                      infl_total=infl_total, infl_ann=infl_ann, real=real, usd=usd_info, period=real_period,
                      catalog=cat), default=str, ensure_ascii=False, indent=1))

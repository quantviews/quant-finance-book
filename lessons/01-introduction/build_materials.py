"""Build student materials from the lesson snapshot exported from moexutils. No instructor answers here.

Run from the book root: python lessons/01-introduction/build_materials.py
Requires the book environment and nbformat (installed with Jupyter).
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import nbformat as nbf
import pandas as pd

HERE = Path(__file__).resolve().parent
BOOK = HERE.parents[1]

BLUE, ORANGE, GREEN = "#34699A", "#C8702A", "#3F8F5B"
font_dir = BOOK / "fonts" / "ibm-plex-sans"
for filename in ["IBMPlexSans-Regular.ttf", "IBMPlexSans-SemiBold.ttf"]:
    font_manager.fontManager.addfont(str(font_dir / filename))
plt.rcParams.update({"font.family": "IBM Plex Sans", "font.size": 15,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.spines.bottom": False,
                     "axes.grid": True, "grid.color": "#D6DDE6", "grid.alpha": .65,
                     "axes.axisbelow": True, "svg.fonttype": "path"})

source_info = json.loads((HERE / "data" / "source.json").read_text(encoding="utf-8"))
df = pd.read_parquet(HERE / "data" / "stocks-source.parquet")
df["date"] = pd.to_datetime(df["date"])
prices = df.pivot(index="date", columns="ticker", values="adj_close")[["SBER", "LKOH"]]
close = df.pivot(index="date", columns="ticker", values="close")[["SBER", "LKOH"]]
export = pd.concat([prices, close.add_suffix("_close")], axis=1).sort_index()
assert export.notna().all().all() and export.index.is_unique
assert (export > 0).all().all()
# LF line endings: the SHA256 must match the raw file on GitHub (see .gitattributes).
csv = export.to_csv(date_format="%Y-%m-%d", float_format="%.8f", lineterminator="\n").encode("utf-8")
DATA_URL = ("https://raw.githubusercontent.com/quantviews/quant-finance-book/main/"
            "lessons/01-introduction/data/prices_2021_2026.csv")
(HERE / "data" / "prices_2021_2026.csv").write_bytes(csv)
# Use exactly the student values in the lecture figures and computed labels.
export = pd.read_csv(HERE / "data" / "prices_2021_2026.csv", parse_dates=["date"]).set_index("date")
prices = export[["SBER", "LKOH"]]
wealth = 100 * prices / prices.iloc[0]
drawdown = wealth / wealth.cummax() - 1
# Reconstruct an index consistent with CBR accrual conventions:
# compound at the next fixing, simple interest between fixings, actual/actual.
# Start before the lesson period so an initial holiday interval is handled correctly.
ruonia = pd.read_parquet(HERE / "data" / "ruonia-source.parquet").set_index("date")["rate"].sort_index()
assert ruonia.index.is_unique and ruonia.notna().all()
assert ruonia.index[0] <= prices.index[0]
value, anchor, accrual, rate = 1.0, 1.0, 0.0, None
levels = {}
for day in pd.date_range(ruonia.index[0], prices.index[-1]):
    if day in ruonia.index:
        anchor, accrual, rate = value, 0.0, ruonia.loc[day] / 100
    levels[day] = value  # Value at date day, before interest for that day.
    accrual += 1 / (366 if day.is_leap_year else 365)
    value = anchor * (1 + rate * accrual)
ruonia_index = pd.Series(levels)
ruonia_wealth = (100 * ruonia_index / ruonia_index.loc[prices.index[0]]).reindex(prices.index)
assert ruonia_wealth.notna().all() and ruonia_wealth.iloc[0] == 100
years = (prices.index[-1] - prices.index[0]).days / 365.25
cagr = lambda end: (end / 100) ** (1 / years) - 1
metadata = {"lesson_date": "2026-11-05", "source": source_info["source"],
            "snapshot_built": source_info["exported"],
            "start": str(prices.index.min().date()), "end": str(prices.index.max().date()),
            "rows": len(prices), "sha256": hashlib.sha256(csv).hexdigest(),
            "fields": {"SBER": "adj_close", "LKOH": "adj_close",
                       "SBER_close": "close, split-adjusted", "LKOH_close": "close, split-adjusted"}}
(HERE / "data" / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")

def chart(series, filename, ylabel, baseline=None):
    fig, ax = plt.subplots(figsize=(11.8, 4.4), layout="constrained")
    for (label, values), color in zip(series.items(), [BLUE, ORANGE, GREEN]):
        ax.plot(values.index, values, lw=2.2, label=label, color=color)
    if baseline is not None:
        ax.axhline(baseline, color="#64748B", lw=.8)
    ax.set_ylabel(ylabel)
    ax.set_xlim(prices.index[0], prices.index[-1])
    ax.legend(frameon=False, ncol=len(series), loc="lower left", bbox_to_anchor=(0, 1.01))
    fig.savefig(HERE / "figures" / filename)
    plt.close(fig)

chart({"Вложение А": wealth["SBER"], "Вложение Б": wealth["LKOH"]}, "paths.svg", "Начальная величина = 100", 100)
chart({"Вложение А": 100*drawdown["SBER"], "Вложение Б": 100*drawdown["LKOH"]}, "drawdown.svg", "От максимума, %", 0)
price_only = 100 * export["SBER_close"] / export["SBER_close"].iloc[0]
chart({"SBER": wealth["SBER"], "LKOH": wealth["LKOH"], "RUONIA": ruonia_wealth},
      "ruonia.svg", "Начальная величина = 100", 100)
chart({"Цена SBER": price_only, "С поправкой на дивиденды": wealth["SBER"]}, "dividends.svg", "Начальная величина = 100", 100)
fmt = lambda x: f"{x:.1f}".replace(".", ",")
pct = lambda x: f"{100 * x:.1f}".replace(".", ",") + "%"
period_label = prices.index.min().strftime("%d.%m.%Y") + "–" + prices.index.max().strftime("%d.%m.%Y")
end_label = prices.index.max().strftime("%d.%m.%Y")
export_label = pd.Timestamp(source_info["exported"]).strftime("%d.%m.%Y")
case = f'''## Два вложения: какое выберете?

В начале периода у каждого было **100 условных единиц**.

::: {{.columns}}
::: {{.column width="48%"}}
### Вложение А

::: {{.big}}
{fmt(wealth['SBER'].iloc[-1])}
:::

в конце периода
:::
::: {{.column width="48%"}}
### Вложение Б

::: {{.big}}
{fmt(wealth['LKOH'].iloc[-1])}
:::

в конце периода
:::
:::

::: {{.prompt}}
Какой информации вам не хватает для выбора?
:::

::: {{.source}}
Источник: Московская биржа, moexutils · {period_label}. До налогов и издержек.
:::

## Теперь видим весь путь

![](figures/paths.svg){{.chart}}

::: {{.prompt}}
В какой момент было бы труднее всего продолжать держать вложение?
:::

::: {{.source}}
Дневные скорректированные ряды. Во время перерыва торгов в 2022 г. линия соединяет доступные наблюдения.
:::

## За буквами стоят реальные акции

| Вложение | Тикер | Что использовано |
|---|---|---|
| А | SBER | Ряд с поправками на сплиты и дивиденды |
| Б | LKOH | Ряд с теми же видами поправок |

Чтобы сравнить траектории, приводим их к одной начальной величине:

**Нормированное значение = 100 × значение в дату / значение в первую дату.**

::: {{.small}}
Это исторический пример двух заранее выбранных акций. Он не показывает, какую бумагу следовало бы выбрать заранее или покупать сейчас.
:::

::: {{.source}}
Источник: Московская биржа, moexutils. Ряды скорректированы на сплиты и дивиденды.
:::

## Итоговый рост не показывает глубину падения

![](figures/drawdown.svg){{.chart}}

**Просадка** – снижение от максимального значения, достигнутого к этой дате.

::: {{.source}}
Расчёт по доступным дневным наблюдениям, {period_label}. Внутридневные падения могут быть глубже.
:::

## Цена акции и результат с дивидендами различаются

![](figures/dividends.svg){{.chart}}

Чтобы сравнение было честным, выплаты обеих бумаг нужно учитывать одинаково.

::: {{.source}}
SBER, {period_label}. adj_close – аналитическая корректировка; это приближение реинвестирования до налогов и издержек, а не цена сделки.
:::

## Сравним с денежным рынком

![](figures/ruonia.svg){{.chart}}

Расчётный ориентир RUONIA: 100 → **{fmt(ruonia_wealth.iloc[-1])}**, {pct(cagr(ruonia_wealth.iloc[-1]))} в год. SBER – {pct(cagr(wealth['SBER'].iloc[-1]))}, LKOH – {pct(cagr(wealth['LKOH'].iloc[-1]))} в год.

::: {{.source}}
Расчёт по ставкам [RUONIA Банка России](https://cbr.ru/hd_base/ruonia/method/): капитализация по датам ставок, простые проценты между ними, база 365/366. Это ориентир, а не доступный вклад или гарантия дохода. {period_label}, до налогов и издержек.
:::
'''
(HERE / "_case.qmd").write_text(case,encoding="utf-8")

md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.metadata.update({"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python"}, "colab": {"name": "practice-01.ipynb"}})
nb.cells = [
md('''# Практика 1. Первое исследование на финансовых данных
**Количественные финансы · НИУ ВШЭ · 5 ноября 2026**

Сегодня сравниваем два исторических ряда, проверяем данные и учимся объяснять график.
Основная часть рассчитана на 80 минут. Обязательные задания: 1–3. Дополнительные задания – по желанию.

Сохраните свою копию, заполните имя и группу. Здесь нет токенов, API и персональных данных.
Книга: https://quantviews.github.io/quant-finance-book/

**Имя и группа:** …'''),
md('''## 1. Как работать с ноутбуком
Ячейка может содержать текст или код. **Shift + Enter** запускает текущую ячейку.
Выполняйте код сверху вниз. После изменения первой даты нужно повторить все зависимые расчёты.

Ноутбук открывается в Jupyter или Google Colab. Данные загружаются по ссылке из репозитория книги на GitHub. Без интернета ноутбук читает файл `data/prices_2021_2026.csv`, если он лежит рядом с ноутбуком (он есть в архиве занятия).
Для локальной работы заранее установите `pandas`, `matplotlib` и `jupyter`.
Если ячейка завершилась ошибкой, прочитайте последнюю строку сообщения и проверьте, выполнены ли предыдущие ячейки.'''),
code('''import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({"figure.figsize": (10, 4), "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False})
print("Библиотеки загружены")'''),
md(f'''## 2. Подготовленный снимок
Дневные наблюдения за 2021–2026 годы. Точная первая и последняя даты будут видны в таблице.
Снимок занятия выгружен {export_label}, последняя доступная дата – {end_label}. 2026 год представлен не полностью. Источник: Московская биржа, поправки на дивиденды – расчёт автора. Снимок свежее данных книги, поэтому числа могут отличаться от примеров в главах.

- `date` – дата наблюдения.
- `SBER`, `LKOH` – `adj_close`, ряды с поправкой на сплиты и дивиденды.
- `SBER_close`, `LKOH_close` – цены с поправкой на сплиты, без дивидендной корректировки.

SBER: ПАО «Сбербанк», ИНН 7707083893. LKOH: ПАО «ЛУКОЙЛ», ИНН 7708004767.

`adj_close` подходит для сравнения относительных изменений. Его уровень не является исторической ценой покупки. Поправка на дивиденды приближает реинвестирование до налогов и издержек.

**Следующая ячейка загружает данные. Выполните её один раз, редактировать не нужно.**'''),
code(f'''# Загрузка данных: сначала с GitHub, без сети – из файла рядом с ноутбуком.
import hashlib, io, urllib.request
from pathlib import Path

URL = "{DATA_URL}"
LOCAL = Path("data/prices_2021_2026.csv")
try:
    raw = urllib.request.urlopen(URL, timeout=20).read()
    print("Данные загружены с GitHub")
except OSError:
    raw = LOCAL.read_bytes()
    print("Нет доступа к GitHub, данные прочитаны из файла", LOCAL)
assert hashlib.sha256(raw).hexdigest() == "{metadata['sha256']}", "Файл отличается от снимка занятия"
df = pd.read_csv(io.BytesIO(raw), parse_dates=["date"])
print("Строк загружено:", len(df))''',metadata={"tags":["setup"]}),
code('''df.head()'''),
md('''### Задание 1. Сначала проверьте таблицу
Определите число строк, первую и последнюю даты, наличие пропусков и повторяющихся дат.
Объясните, почему здесь нет всех календарных дней. Можно ли только по отсутствующей дате понять причину отсутствия торгов?

Используйте результат следующей ячейки. **Ваш вывод:** …'''),
code('''print("Строк:", len(df))
print("Первая дата:", df["date"].min().date())
print("Последняя дата:", df["date"].max().date())
print("Повторяющихся дат:", df["date"].duplicated().sum())
print("Пропусков по столбцам:")
print(df.isna().sum())'''),
md('''Теперь найдите **самый большой разрыв** между соседними датами. `df["date"].diff()` считает разницу с предыдущей строкой; найдите её максимум и строку, где он достигается (`.idxmax()`).
Между какими датами этот разрыв и что тогда происходило на рынке?

**Ваш вывод:** …'''),
code('''# Найдите самый большой разрыв между соседними датами.
gaps = df["date"].diff()
'''),
md('''## 3. Один график – одна понятная величина
Сделаем даты индексом таблицы. До запуска предскажите: что означает деление на первую строку?

После нормирования обе линии начинаются со 100. Высота линии показывает относительное изменение от начала выбранного периода, а не цену акции в рублях.'''),
code('''prices = df.set_index("date")[["SBER", "LKOH"]].sort_index()
normalized = 100 * prices / prices.iloc[0]
ax = normalized.plot(color=["#34699A", "#C8702A"])
ax.set(title="Сравнение скорректированных рядов", xlabel="Дата",
       ylabel="Начальная величина = 100")
ax.grid(alpha=0.25)
plt.show()'''),
md('''## 4. Разобранный пример: изменение SBER за весь период
Изменение за период = последнее значение / первое значение − 1.

`.iloc[0]` выбирает первую строку, `.iloc[-1]` – последнюю. В расчётах доля 0.10 означает 10%. Формат `:.1%` меняет только отображение.
Полученная величина относится ко всему периоду, а не к одному году.
Чтобы сравнить её с годовой ставкой, пересчитаем в среднегодовую: (1 + изменение за период)^(1 / число лет) − 1. Делить на число лет нельзя: доход каждого года начисляется на уже выросшую сумму.'''),
code('''ticker = "SBER"
first = prices[ticker].iloc[0]
last = prices[ticker].iloc[-1]
period_return = last / first - 1
print(f"{ticker}: изменение за весь период {period_return:.1%}")

years = (prices.index[-1] - prices.index[0]).days / 365.25
annual = (1 + period_return) ** (1 / years) - 1
print(f"Лет: {years:.2f}; в среднем за год {annual:.1%}")'''),
md(f'''### Задание 2. Повторите расчёт для LKOH
1. Посчитайте изменение LKOH за тот же период и среднегодовую величину.
2. Сравните с результатом SBER и положением линий в конце графика.
3. Расчётный ориентир по RUONIA за тот же период вырос в среднем на {pct(cagr(ruonia_wealth.iloc[-1]))} в год. Это не доходность доступного вклада и не гарантия результата. Что это говорит о результатах двух акций?
4. Объясните, почему из этого не следует, что LKOH обязательно будет лучше в будущем.

**Ваш вывод:** …'''),
code('''# Напишите свой расчёт для LKOH.
# Подсказка: используйте пример выше и замените тикер.
'''),
md('''### Задание 3. Меняем начальную дату
Сначала предположите, сохранится ли порядок результатов.
Ниже выделен период с 2023 года. Постройте заново нормированные линии и повторите сравнение двух акций.

**Важно:** первая строка для нормирования теперь должна принадлежать новой выборке.

**Ваше предположение:** …

**Что получилось и как изменился вывод:** …'''),
code('''start = "2023-01-01"
subset = prices.loc[start:]
print("Фактическая первая дата:", subset.index.min().date())
# Допишите нормирование, график и изменение каждой серии за новый период.
'''),
md('''## 5. Три предложения вместо подписи «всё выросло»
Завершите вывод:
1. На периоде … мы сравнили … и получили …
2. После изменения начальной даты …
3. Этот расчёт не учитывает … и не позволяет утверждать …

Если использовали ИИ, запишите: **что спросили**, **что получили**, **как проверили**.

**Мой текст:** …'''),
md('''### Дополнительно. Падение от достигнутого максимума
Как мог бы чувствовать себя инвестор, купивший бумагу возле предыдущего максимума?
Для каждой даты нужен максимум только по прошлой истории, включая текущую дату.
Подсказка: `.cummax()` вычисляет такой максимум. Просадка = текущее значение / накопленный максимум − 1.

Найдите минимальную просадку каждого ряда и её дату. Поясните, почему это другая величина, чем изменение от начала выборки.

**Ваш вывод:** …'''),
code('''# Необязательное задание: рассчитайте просадку и дату её минимума.
'''),
md('''### Дополнительно. Что дали дивиденды
Столбцы `SBER_close` и `LKOH_close` – цены без поправки на дивиденды. Посчитайте по ним изменение за весь период и сравните с результатом по `SBER` и `LKOH`.
На сколько процентных пунктов различаются результаты с дивидендной корректировкой и без неё? Это разница двух расчётов, включающая эффект реинвестирования, а не сумма полученных дивидендов. Постройте на одном графике нормированные `SBER` и `SBER_close`: как меняется разрыв около дивидендных отсечек? Почему он может меняться и между ними?

**Ваш вывод:** …'''),
code('''# Необязательное задание: сравните результат с дивидендами и без них.
'''),
md('''## Перед сдачей
- Перезапустите ядро и выполните все ячейки сверху вниз.
- Проверьте, что обязательные задания 1–3 выполнены, а выводы написаны своими словами.
- Сохраните файл `practice01_фамилия.ipynb` и сдайте способом, который объявит преподаватель.
- Не включайте в файл пароли, токены или личные финансовые данные.

**12 ноября очного занятия не будет.** Вместо него выполните самостоятельную работу `practice-02-self-study.ipynb` из раздела материалов занятий. Сначала завершите задания 1–3 этой практики. Способ и срок сдачи преподаватель объявит отдельно.

Если Python для вас новый, непонятные строки кода разберите по приложению A учебника «Основы Python для финансиста»: https://quantviews.github.io/quant-finance-book/appendix-python.html''')]
nbf.validate(nb)
nbf.write(nb, HERE / "practice-01.ipynb")
print(f"Created {len(nb.cells)} cells; {len(prices)} daily rows; CSV SHA256 {metadata['sha256']}")

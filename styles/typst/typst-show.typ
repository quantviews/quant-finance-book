// Оформление PDF-версии книги (Typst).
//
// Собственный шаблон учебника. Заменяет штатный partial typst-show.typ
// расширения orange-book, которое Quarto подключает к книгам в Typst.
// От orange-book остаётся только Lua-фильтр: он превращает части книги
// в вызовы #part[...] и приложения в #show: appendices.with(...),
// поэтому функции part и appendices определены здесь с той же сигнатурой.

// ---- Шрифты и цвета ----------------------------------------------------------
#let font-body = ("STIX Two Text",)
#let font-sans = ("IBM Plex Sans", "STIX Two Text")
#let font-mono = ("JetBrains Mono",)
#let font-math = ("STIX Two Math",)

#let accent = brand-color.at("navy", default: rgb("#23415F"))
#let accent-2 = brand-color.at("blue", default: rgb("#34699A"))
#let muted = rgb("#6B7280")
#let rule-color = rgb("#C9CED6")

#let book-title = [$if(title)$$title$$endif$]
#let book-subtitle = [$if(subtitle)$$subtitle$$endif$]
#let book-author = [$if(by-author)$$for(by-author)$$it.name.literal$$sep$, $endfor$$endif$]
#let book-date = [$if(date)$$date$$endif$]

// ---- Служебные метки ---------------------------------------------------------
// <qf-break> ставится перед разрывом страницы у главы или части,
// <qf-start> – на первой странице главы или части. Страницы между ними пустые:
// на них не печатаются колонтитулы.
#let appendix-state = state("appendix-state", none)
#let part-counter = counter("qf-part")

#let is-start-page(p) = query(<qf-start>).any(m => m.location().page() == p)
#let is-blank-page(p) = {
  let breaks = query(<qf-break>)
  let starts = query(<qf-start>)
  range(calc.min(breaks.len(), starts.len())).any(i => {
    breaks.at(i).location().page() < p and p < starts.at(i).location().page()
  })
}

// ---- Части и приложения (вызываются фильтром orange-book) -------------------
#let part(title) = {
  part-counter.step()
  [#metadata(none)<qf-break>]
  pagebreak(to: "odd", weak: true)
  [#metadata(none)<qf-start>]
  context {
    let n = part-counter.get().first()
    [#metadata((title: title, number: n))<qf-part>]
    set par(justify: false)
    v(1fr)
    align(center)[
      #text(font: font-sans, size: 11pt, weight: "semibold", fill: accent-2, tracking: 0.12em)[
        #upper[Часть #numbering("I", n)]
      ]
      #v(0.8em)
      #line(length: 30mm, stroke: 1.2pt + accent-2)
      #v(0.8em)
      #text(font: font-sans, size: 24pt, weight: "semibold", fill: accent, hyphenate: false)[#title]
    ]
    v(1.3fr)
  }
}

#let appendices(title, hide-parent: false, body) = {
  appendix-state.update(title)
  counter(heading).update(0)
  set heading(numbering: (..n) => {
    let v = n.pos()
    if v.len() == 1 { numbering("A", ..v) } else if v.len() <= 3 { numbering("A.1", ..v) }
  })
  body
}

// ---- Обложка и оборот титула -------------------------------------------------
#let title-page() = {
  page(margin: (left: 26mm, right: 22mm, top: 32mm, bottom: 28mm), header: none, footer: none)[
    #set par(justify: false)
    #text(font: font-sans, size: 13pt, fill: muted)[#book-author]
    #v(1fr)
    #box(width: 22mm, height: 3pt, fill: accent-2)
    #v(10pt)
    #text(font: font-sans, size: 34pt, weight: "semibold", fill: accent, hyphenate: false)[#book-title]
    #v(12pt)
    #text(font: font-body, size: 16pt, style: "italic", fill: accent)[#book-subtitle]
    #v(1.6fr)
    #text(font: font-sans, size: 10pt, fill: muted)[
      Учебник к курсу «Количественные финансы» \
      НИУ ВШЭ, факультет мировой экономики и мировой политики
    ]
    #v(6pt)
    #text(font: font-sans, size: 10pt, fill: muted)[Москва · #book-date]
  ]
  page(header: none, footer: none)[
    #set text(size: 8.5pt, fill: muted)
    #set par(justify: false, spacing: 0.9em)
    #v(1fr)
    *#book-author* \
    #book-title. #book-subtitle. – Москва, #book-date.

    Книга знакомит с количественными методами анализа финансовых данных на примерах российского рынка: доходность и риск, отчётность компаний, модели временных рядов, портфели, облигации, проверка торговых стратегий. Примеры кода приводятся на Python; онлайн-версия содержит также код на R.

    Код, данные и онлайн-версия книги: #link("https://github.com/quantviews/quant-finance-book")[github.com/quantviews/quant-finance-book]

    © #book-author, #book-date. Текст распространяется на условиях лицензии
    #link("https://creativecommons.org/licenses/by-sa/4.0/deed.ru")[CC BY-SA 4.0].
  ]
}

// ---- Оглавление ---------------------------------------------------------------
#let toc-page-num(loc) = {
  let pat = loc.page-numbering()
  if pat == none { pat = "1" }
  numbering(pat, ..counter(page).at(loc))
}

#let toc-row(loc, indent: 0pt, num: none, num-width: 0pt, body, fill: none, weight: "regular", font: font-body, size: 10pt, above: 0.45em) = {
  block(above: above, below: 0pt, link(loc)[
    #set text(font: font, size: size, weight: weight)
    #grid(
      columns: (indent, num-width, 1fr, auto),
      column-gutter: (0pt, 0pt, 4pt),
      [], [#num], [#body #box(width: 1fr, fill)], [#toc-page-num(loc)],
    )
  ])
}

#let table-of-contents(depth: 2) = {
  page(header: none)[
    #text(font: font-sans, size: 24pt, weight: "semibold", fill: accent)[Оглавление]
    #v(0.4em)
    #line(length: 100%, stroke: 0.6pt + rule-color)
    #v(1.2em)
    #context {
      let items = query(
        selector(<qf-part>)
          .or(heading.where(level: 1, outlined: true))
          .or(heading.where(level: 2, outlined: true)),
      )
      for it in items {
        let loc = it.location()
        if it.func() == metadata {
          let v = it.value
          block(above: 1.5em, below: 0.5em, link(loc)[
            #set text(font: font-sans, size: 9.5pt, weight: "semibold", fill: accent-2, tracking: 0.08em)
            #upper[Часть #numbering("I", v.number). #v.title]
          ])
        } else if it.level == 1 {
          let num = if it.numbering != none { numbering(it.numbering, ..counter(heading).at(loc)) }
          toc-row(loc, num: num, num-width: 2.2em, it.body, weight: "semibold",
                  font: font-sans, size: 10pt, above: 1em)
        } else if depth >= 2 {
          let num = if it.numbering != none { numbering(it.numbering, ..counter(heading).at(loc)) }
          toc-row(loc, indent: 2.2em, num: num, num-width: 2.6em, it.body,
                  fill: repeat(text(fill: rule-color)[.#h(4pt)]), size: 10pt)
        }
      }
    }
  ]
}

// ---- Колонтитулы ---------------------------------------------------------------
#let running-header() = context {
  let p = here().page()
  if is-start-page(p) or is-blank-page(p) { return }
  let chapters = query(heading.where(level: 1).before(here()))
  if chapters.len() == 0 { return }
  let ch = chapters.last()
  set text(font: font-sans, size: 8.5pt, fill: muted)
  let pn = counter(page).display()
  let left-text = if ch.numbering != none {
    [#numbering(ch.numbering, ..counter(heading).at(ch.location())). #ch.body]
  } else { ch.body }
  let right-text = {
    let secs = query(heading.where(level: 2).before(here()))
    if secs.len() > 0 and secs.last().location().page() >= ch.location().page() {
      let s = secs.last()
      if s.numbering != none [#numbering(s.numbering, ..counter(heading).at(s.location())) #s.body] else { s.body }
    } else { left-text }
  }
  block(width: 100%, inset: (bottom: 4pt), stroke: (bottom: 0.4pt + rule-color))[
    #if calc.even(p) [#pn #h(1em) #left-text #h(1fr)] else [#h(1fr) #right-text #h(1em) #pn]
  ]
}

#let running-footer() = context {
  let p = here().page()
  if is-start-page(p) and not is-blank-page(p) {
    align(center, text(font: font-sans, size: 8.5pt, fill: muted, counter(page).display()))
  }
}

// ---- Врезки (callout) ------------------------------------------------------------
// Переопределяет функцию Quarto: вместо плашки с рамкой и иконкой – полоса слева,
// светлый фон того же оттенка и заголовок шрифтом без засечек.
#let callout(body: [], title: "Callout", background_color: rgb("#dddddd"), icon: none,
             icon_color: black, body_background_color: white) = {
  let c = color.mix((icon_color, 50%), (accent, 50%), space: rgb)
  block(
    width: 100%,
    breakable: true,
    fill: color.mix((c, 7%), (white, 93%), space: rgb),
    stroke: (left: 2.5pt + c),
    inset: (left: 12pt, right: 11pt, top: 9pt, bottom: 10pt),
    above: 1.5em,
    below: 1.5em,
  )[
    #block(below: 0.7em, sticky: true,
      text(font: font-sans, size: 9.5pt, weight: "semibold", fill: c.darken(15%), title))
    #set text(size: 0.95em)
    #set par(spacing: 0.8em)
    #body
  ]
}

// ---- Основные настройки ----------------------------------------------------------
#set document(title: book-title, author: "$for(by-author)$$it.name.literal$$sep$, $endfor$")
#set page(
  paper: "iso-b5",
  margin: (inside: 24mm, outside: 18mm, top: 24mm, bottom: 22mm),
  header: running-header(),
  footer: running-footer(),
  header-ascent: 40%,
)
#set text(font: font-body, size: 10.5pt, lang: "ru", hyphenate: true)
#set par(justify: true, leading: 0.62em, spacing: 1.05em, first-line-indent: 0pt)
#show math.equation: set text(font: font-math)
#show raw: set text(font: font-mono, size: 0.84em)
#show link: set text(fill: accent-2)

// Списки: пункты ближе друг к другу, чем абзацы.
#set list(indent: 0.4em, body-indent: 0.5em, spacing: 0.6em, marker: ([•], [–]))
#set enum(indent: 0.4em, body-indent: 0.5em, spacing: 0.6em)

// Таблицы: мельче шрифт, воздух в ячейках, линии в стиле booktabs.
#set table(
  inset: (x: 5pt, y: 4.5pt),
  stroke: (x, y) => if y > 0 { (top: 0.3pt + rule-color) },
)
#show table: set text(size: 0.86em)
#show table: set par(justify: false, leading: 0.5em)
#show table.cell.where(y: 0): set text(font: font-sans, weight: "semibold", size: 0.95em)
#show table: it => block(stroke: (top: 0.8pt + accent, bottom: 0.8pt + accent), it)

// Рисунки и таблицы: подписи шрифтом без засечек, нумерация по главам.
#set figure(numbering: n => {
  let pat = if appendix-state.get() != none { "A.1" } else { "1.1" }
  numbering(pat, counter(heading).get().first(), n)
})
#set figure.caption(separator: [. ])
#show figure.caption: set text(font: font-sans, size: 8.5pt)
#show figure: set block(above: 1.4em, below: 1.4em)

// Заголовки.
#set heading(numbering: (..n) => {
  let v = n.pos()
  if v.len() == 1 { numbering("1", ..v) } else if v.len() <= 3 { numbering("1.1", ..v) }
})
#show heading: set text(font: font-sans, fill: accent, hyphenate: false)
#show heading: set par(justify: false)

// Заголовок с висячим номером: при переносе строки текст выравнивается
// по тексту, а не по номеру.
#let numbered-title(it, gap: 0.6em) = {
  // Код в заголовке – почти того же размера, что и текст заголовка
  // (по умолчанию моноширинный шрифт уменьшен до 0,84 основного).
  show raw: set text(size: 0.95em / 0.84)
  if it.numbering == none { return it.body }
  grid(
    columns: (auto, 1fr),
    column-gutter: gap,
    text(fill: accent-2)[#counter(heading).display()],
    it.body,
  )
}

#show heading.where(level: 1): it => {
  [#metadata(none)<qf-break>]
  pagebreak(to: "odd", weak: true)
  [#metadata(none)<qf-start>]
  v(22mm)
  block(below: 0pt, text(size: 24pt, weight: "semibold", numbered-title(it, gap: 0.45em)))
  v(10pt)
  line(length: 100%, stroke: 0.8pt + accent-2)
  v(14mm)
}

#show heading.where(level: 2): it => {
  set text(size: 13.5pt, weight: "semibold")
  block(above: 2em, below: 0.9em, sticky: true, numbered-title(it, gap: 0.7em))
}

#show heading.where(level: 3): it => {
  set text(size: 11.5pt, weight: "semibold")
  block(above: 1.6em, below: 0.8em, sticky: true, numbered-title(it, gap: 0.6em))
}

#show heading.where(level: 4): it => {
  set text(size: 10.5pt, weight: "semibold")
  block(above: 1.3em, below: 0.7em, sticky: true, it.body)
}
#show heading.where(level: 4): set heading(numbering: none, outlined: false)

// ---- Начало книги ------------------------------------------------------------------
#title-page()
#set page(numbering: "i")
#counter(page).update(1)
#table-of-contents(depth: $if(toc-depth)$$toc-depth$$else$2$endif$)
#pagebreak(to: "odd", weak: true)
#set page(numbering: "1")
#counter(page).update(1)

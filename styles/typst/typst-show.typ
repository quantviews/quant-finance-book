// Оформление PDF-версии книги (Typst).
//
// Основа – пакет orange-book, встроенный в Quarto для книг в Typst.
// Этот partial заменяет штатный typst-show.typ расширения orange-book:
// задаёт формат страницы, шрифты и русские подписи.

#import "@preview/orange-book:0.7.1": book, part, chapter, appendices

// ---- Шрифты (файлы лежат в fonts/) -----------------------------------------
#let font-body = ("STIX Two Text",)
#let font-sans = ("IBM Plex Sans", "STIX Two Text")
#let font-mono = ("JetBrains Mono",)
#let font-math = ("STIX Two Math",)

// ---- Цвета из _brand.yaml ----------------------------------------------------
#let accent = brand-color.at("navy", default: brand-color.at("primary", default: navy))

#set text(font: font-body, hyphenate: true)
#show math.equation: set text(font: font-math)
#show heading: set text(font: font-sans, hyphenate: false)
#show outline.entry: set text(font: font-sans)
#show figure.caption: set text(font: font-sans, size: 0.9em)

// Код: моноширинный шрифт чуть меньше основного.
// (Подсвеченный код Quarto собирает из инлайн-фрагментов raw, поэтому
// оформлять raw.where(block: false) рамками нельзя: ломаются строки.)
#show raw: set text(font: font-mono, size: 0.84em)

#show: book.with(
$if(title)$
  title: [$title$],
$endif$
$if(subtitle)$
  subtitle: [$subtitle$],
$endif$
$if(by-author)$
  author: "$for(by-author)$$it.name.literal$$sep$, $endfor$",
$endif$
$if(date)$
  date: "$date$",
$endif$
  lang: "ru",
  paper-size: "iso-b5",
  margin: (inside: 24mm, outside: 20mm, top: 24mm, bottom: 22mm),
  font-size: 10.5pt,
  main-color: accent,
  heading-style: 2,
  supplement-chapter: "Глава",
  supplement-part: "Часть",
  outline-depth: $if(toc-depth)$$toc-depth$$else$2$endif$,
  copyright: [
    #set text(font: font-sans, size: 8.5pt)
    © $if(by-author)$$for(by-author)$$it.name.literal$$sep$, $endfor$$endif$, $if(date)$$date$$endif$.

    Книга распространяется под лицензией
    #link("https://creativecommons.org/licenses/by-sa/4.0/deed.ru")[CC BY-SA 4.0].
  ],
)

// Межстрочный интервал основного текста.
#set par(leading: 0.62em, spacing: 0.62em)

// Нумеруем заголовки только до 3-го уровня (как number-depth в HTML).
#show heading.where(level: 4): set heading(numbering: none, outlined: false)

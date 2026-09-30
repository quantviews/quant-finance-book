-- Печатная версия (PDF):
-- * из вкладок .panel-tabset остаётся только первая (Python), остальные (R)
--   показываются только в HTML; заголовки вкладок убираются, чтобы они
--   не становились разделами книги;
-- * заметки на полях (.column-margin) печатаются в тексте мелким шрифтом
--   с тонкой линией слева.

if quarto.doc.is_format("html") then
  return {}
end

local function is_tab_header(el, level)
  return el.t == "Header" and (level == nil or el.level == level)
end

local function margin_note(div)
  local out = pandoc.List()
  out:insert(pandoc.RawBlock("typst",
    '#block(inset: (left: 9pt, y: 2pt), stroke: (left: 0.6pt + rgb("#9CA3AF")), above: 1em, below: 1em)[\n' ..
    '#set text(font: ("IBM Plex Sans", "STIX Two Text"), size: 8.5pt, fill: rgb("#4B5563"))\n' ..
    '#set par(justify: false, spacing: 0.6em)\n'))
  out:extend(div.content)
  out:insert(pandoc.RawBlock("typst", "]"))
  return out
end

function Div(div)
  if div.classes:includes("column-margin") then
    return margin_note(div)
  end
  if not div.classes:includes("panel-tabset") then
    return nil
  end
  local blocks = div.content
  local first = nil
  for _, b in ipairs(blocks) do
    if is_tab_header(b) then
      first = b.level
      break
    end
  end
  if first == nil then
    return nil
  end

  local out = pandoc.List()
  local tab = 0
  local names = pandoc.List()
  for _, b in ipairs(blocks) do
    if is_tab_header(b, first) then
      tab = tab + 1
      if tab > 1 then
        names:insert(pandoc.utils.stringify(b.content))
      end
    elseif tab == 1 then
      out:insert(b)
    end
  end
  if #names > 0 then
    out:insert(pandoc.Para({
      pandoc.Emph(pandoc.Str("Вариант кода на " .. table.concat(names, ", ") ..
        " – в онлайн-версии книги."))
    }))
  end
  return out
end

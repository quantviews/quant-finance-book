-- Печатная версия (PDF): из вкладок .panel-tabset оставляем только первую
-- (Python), остальные (R) показываются только в HTML.
-- Заголовки вкладок убираются, чтобы они не становились разделами книги.

if quarto.doc.is_format("html") then
  return {}
end

local function is_tab_header(el, level)
  return el.t == "Header" and (level == nil or el.level == level)
end

function Div(div)
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

# Общие настройки для всех глав. Подключается первым чанком каждой главы:
#
# ```{r}
# #| include: false
# source("_common.R")
# ```

knitr::opts_chunk$set(
  comment = "#>",
  collapse = TRUE,
  fig.align = "center"
)

# Python-чанки выполняются через reticulate в conda-окружении py312.
library(reticulate)   # py$... – доступ к Python-объектам из R и инлайн-кода
use_condaenv("py312", required = TRUE)

# Загрузчик учебных данных (R/qf.R); в Python – модуль qf.
source(file.path("R", "qf.R"), encoding = "UTF-8")

# Единый стиль графиков: matplotlib (qf/plot.py) и ggplot2.
reticulate::py_run_string("from qf import plot as _qfplot; _qfplot.use_book_style()")
ggplot2::theme_set(
  ggplot2::theme_minimal(base_size = 10) +
    ggplot2::theme(
      plot.title = ggplot2::element_text(face = "bold", hjust = 0),
      panel.grid.minor = ggplot2::element_blank()
    )
)
options(
  ggplot2.discrete.colour = c("#34699A", "#C8702A", "#3F8F5B", "#B8412E", "#23415F", "#6B7280"),
  pillar.bold = TRUE,
  cli.unicode = FALSE,
  width = 80
)

# Числа в тексте (инлайн `r ...`): десятичная запятая, неразрывный пробел в тысячах.
num <- function(x, digits = 1) {
  out <- formatC(x, format = "f", digits = digits, big.mark = "\u00a0", decimal.mark = ",")
  sub("^-", "\u2212", out)   # \u0442\u0438\u043f\u043e\u0433\u0440\u0430\u0444\u0441\u043a\u0438\u0439 \u043c\u0438\u043d\u0443\u0441
}
pct <- function(x, digits = 1) paste0(num(100 * x, digits), "%")
dt <- function(x) format(as.Date(x), "%d.%m.%Y")

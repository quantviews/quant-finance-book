# Загрузка учебных данных книги в R (аналог Python-модуля qf.data).
# Подключается в _common.R; файлы описаны в data/README.md.

qf_data_dir <- function() {
  Sys.getenv("QF_DATA", unset = file.path(here_book(), "data"))
}

here_book <- function() {
  # Корень книги – папка с _quarto.yml (поиск вверх от рабочей папки).
  d <- normalizePath(getwd(), winslash = "/")
  while (!file.exists(file.path(d, "_quarto.yml"))) {
    parent <- dirname(d)
    if (parent == d) stop("Не найден корень книги (_quarto.yml)")
    d <- parent
  }
  d
}

# nanoparquet, а не arrow: Arrow C++ в R конфликтует с pyarrow/polars,
# когда R- и Python-чанки выполняются в одном процессе (reticulate).
qf_read <- function(name, tickers = NULL, start = NULL, end = NULL, date_col = "date") {
  path <- file.path(qf_data_dir(), name)
  if (!file.exists(path)) stop("Нет файла ", path, ". См. data/README.md")
  df <- nanoparquet::read_parquet(path)
  if (!is.null(tickers)) df <- df[df$ticker %in% tickers, ]
  if (!is.null(start)) df <- df[df[[date_col]] >= as.Date(start), ]
  if (!is.null(end)) df <- df[df[[date_col]] <= as.Date(end), ]
  tibble::as_tibble(df)
}

#' Дневные данные акций (длинный формат: date, ticker, ..., adj_close, market_cap)
qf_load_stocks <- function(tickers = NULL, start = NULL, end = NULL) {
  qf_read("stocks.parquet", tickers, start, end)
}

#' Цены в широком формате: date + по столбцу на тикер
qf_load_prices <- function(tickers = NULL, start = NULL, end = NULL, field = "adj_close") {
  qf_load_stocks(tickers, start, end) |>
    dplyr::select(date, ticker, value = dplyr::all_of(field)) |>
    tidyr::pivot_wider(names_from = ticker, values_from = value) |>
    dplyr::arrange(date)
}

qf_load_index <- function(tickers = "IMOEX", start = NULL, end = NULL) {
  qf_read("indexes.parquet", tickers, start, end)
}

qf_load_dividends <- function(tickers = NULL) {
  qf_read("dividends.parquet", tickers, date_col = "closing_date")
}

qf_load_key_rate <- function() qf_read("key_rate.parquet")
qf_load_ruonia <- function(start = NULL, end = NULL) qf_read("ruonia.parquet", NULL, start, end)
qf_load_zcyc <- function(start = NULL, end = NULL) qf_read("zcyc.parquet", NULL, start, end)

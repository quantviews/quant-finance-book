# Run from the book root: Rscript tests/check_micro_time.R
source("R/qf.R", encoding = "UTF-8")
book <- qf_load_micro("sber_book")
stopifnot(format(book$time[1], "%H:%M:%S") == "10:00:01")
noon <- as.POSIXct("2025-12-30 12:00:00", tz = "Europe/Moscow")
stopifnot(sum(book$time == noon) == 1)
stopifnot(all(diff(as.numeric(book$time)) == 1))
cat("Microstructure: Moscow clock and one-second grid OK\n")

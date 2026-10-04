"""Dated-cash-flow bond lab: annual effective yields, ACT/365F, amounts per bond.

Canonical source: moex-analytics/moex_analytics/bonds.py. The book snapshot
exporter copies this standalone module verbatim to qf/bonds.py for offline use.
This is an explicit educational valuation convention, not the MOEX calculator.
"""

import math
from dataclasses import dataclass
from datetime import date, datetime

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp


@dataclass(frozen=True)
class CashFlow:
    payment_date: date
    amount: float


def as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _arrays(flows, valuation_date):
    day = as_date(valuation_date)
    future = []
    for flow in flows:
        amount = float(flow.amount)
        if not math.isfinite(amount) or amount < 0:
            raise ValueError("Cash flows must be finite, nonnegative amounts")
        payment = as_date(flow.payment_date)
        if payment > day and amount > 0:
            future.append(((payment - day).days / 365.0, amount))
    if not future:
        raise ValueError("No positive cash flows strictly after valuation date")
    times, amounts = np.asarray(future, dtype=float).T
    return times, amounts


def dirty_price_from_quote(clean_pct, face_value, accrued):
    """ISS clean quote is % of outstanding nominal; ACCINT is currency per bond."""
    if not all(math.isfinite(float(v)) for v in (clean_pct, face_value, accrued)):
        raise ValueError("Price, nominal and accrued interest must be finite")
    if clean_pct <= 0 or face_value <= 0 or accrued < 0:
        raise ValueError(
            "Require positive clean price/nominal and nonnegative accrued interest"
        )
    return clean_pct / 100 * face_value + accrued


def accrued_interest(valuation_date, period_start, period_end, coupon_amount):
    """Linear accrual of an observed coupon amount over its actual coupon period.

    Diagnostic approximation only; valuation uses the observed ISS ACCINT.
    At the coupon date accrued resets to zero (coupon paid that day excluded).
    """
    day, start, end = map(as_date, (valuation_date, period_start, period_end))
    if not start <= day <= end or end <= start:
        raise ValueError("Valuation date must be inside a positive coupon period")
    if not math.isfinite(coupon_amount) or coupon_amount < 0:
        raise ValueError("Coupon must be finite and nonnegative")
    return (
        0.0 if day == end else coupon_amount * (day - start).days / (end - start).days
    )


def price_from_yield(flows, valuation_date, annual_yield):
    """Dirty price using annual effective yield as a decimal, e.g. .15."""
    if not math.isfinite(annual_yield) or annual_yield <= -1:
        raise ValueError("Annual effective yield must be finite and greater than -1")
    times, amounts = _arrays(flows, valuation_date)
    return float(amounts @ np.exp(-np.log1p(annual_yield) * times))


def yield_to_maturity(flows, valuation_date, dirty_price):
    """Unique annual effective IRR for a positive price and positive future receipts."""
    if not math.isfinite(dirty_price) or dirty_price <= 0:
        raise ValueError("Dirty price must be finite and positive")
    times, amounts = _arrays(flows, valuation_date)
    log_price = math.log(dirty_price)

    def residual(log_rate):
        return logsumexp(np.log(amounts) - log_rate * times) - log_price

    log_rate = brentq(residual, -32, 32, xtol=1e-13)
    return float(np.expm1(log_rate))


def risk_measures(flows, valuation_date, annual_yield):
    """Macaulay years, modified years, convexity years²; DV01 is positive RUB/bp."""
    price = price_from_yield(flows, valuation_date, annual_yield)
    times, amounts = _arrays(flows, valuation_date)
    present = amounts / (1 + annual_yield) ** times
    macaulay = float(times @ present / price)
    modified = macaulay / (1 + annual_yield)
    convexity = float((times * (times + 1)) @ present / price / (1 + annual_yield) ** 2)
    return {
        "dirty_price": price,
        "macaulay_years": macaulay,
        "modified_years": modified,
        "convexity_years2": convexity,
        "dv01": price * modified * 0.0001,
    }


def yield_scenarios(flows, valuation_date, annual_yield, shifts_bps):
    """Exact instantaneous repricing versus duration and convexity approximation."""
    risk = risk_measures(flows, valuation_date, annual_yield)
    rows = []
    for bps in shifts_bps:
        dy = float(bps) / 10000
        new_price = price_from_yield(flows, valuation_date, annual_yield + dy)
        rows.append(
            {
                "shift_bps": float(bps),
                "dirty_price": new_price,
                "change_pct": 100 * (new_price / risk["dirty_price"] - 1),
                "duration_pct": -100 * risk["modified_years"] * dy,
                "duration_convexity_pct": 100
                * (
                    -risk["modified_years"] * dy
                    + 0.5 * risk["convexity_years2"] * dy**2
                ),
            }
        )
    return rows


def zero_rates(times, curve_years, curve_yields):
    """Annual effective decimal spot rates from log-discount interpolation.

    The origin has discount factor 1, implying a flat short-end zero rate
    below the first tenor. No extrapolation beyond the last curve tenor.
    """
    t = np.asarray(times, dtype=float)
    x, y = np.asarray(curve_years, dtype=float), np.asarray(curve_yields, dtype=float)
    if x.ndim != 1 or y.shape != x.shape or len(x) < 2:
        raise ValueError("Need at least two matching curve nodes")
    if not (
        np.isfinite(x).all()
        and np.isfinite(y).all()
        and (x > 0).all()
        and (np.diff(x) > 0).all()
        and (y > -1).all()
    ):
        raise ValueError("Curve tenors must increase; yields must be finite and > -1")
    if not np.isfinite(t).all() or (t < 0).any() or (t > x[-1]).any():
        raise ValueError("Cash flow beyond curve horizon or invalid time")
    log_df = np.interp(t, np.r_[0.0, x], np.r_[0.0, -x * np.log1p(y)])
    return np.expm1(
        np.divide(-log_df, t, out=np.full_like(t, np.log1p(y[0])), where=t > 0)
    )


def price_from_curve(flows, valuation_date, curve_years, curve_yields, spread=0.0):
    """Add spread (decimal) to interpolated annual effective zero rates."""
    times, amounts = _arrays(flows, valuation_date)
    yields = zero_rates(times, curve_years, curve_yields) + spread
    if not np.isfinite(yields).all() or (yields <= -1).any():
        raise ValueError("Shifted spot rates must be finite and > -1")
    return float(amounts @ np.exp(-np.log1p(yields) * times))


def z_spread(flows, valuation_date, dirty_price, curve_years, curve_yields):
    """Model Z-spread, annual effective additive decimal (not ISS ZSPREAD)."""
    if not math.isfinite(dirty_price) or dirty_price <= 0:
        raise ValueError("Dirty price must be finite and positive")
    times, amounts = _arrays(flows, valuation_date)
    base = zero_rates(times, curve_years, curve_yields)

    def residual(spread):
        return logsumexp(np.log(amounts) - times * np.log1p(base + spread)) - math.log(
            dirty_price
        )

    lo, hi = -1 - float(base.min()) + 1e-10, 1.0
    while residual(hi) > 0 and hi < 1e8:
        hi *= 2
    return float(brentq(residual, lo, hi, xtol=1e-13))

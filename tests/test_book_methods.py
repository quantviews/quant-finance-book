"""Regression checks of executable teaching examples, without rendering the book.

Run: python -m pytest tests/test_book_methods.py
"""
import ast
from pathlib import Path
import re

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]


def example_function(chapter, name, **context):
    """Load the actual function from a Python fence, without unrelated chapter I/O."""
    source = (ROOT / chapter).read_text(encoding="utf-8")
    for block in re.findall(r"```\{python\}\s*\n(.*?)\n```", source, re.S):
        for node in ast.parse(block).body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                namespace = {"np": np, "pd": pd, **context}
                exec(compile(ast.Module(body=[node], type_ignores=[]), chapter, "exec"), namespace)
                return namespace[name]
    raise AssertionError(f"Function {name} missing in {chapter}")


def test_es_credit_example_and_fractional_tail():
    es = example_function("10-var-es.qmd", "empirical_es")
    # Four defaults out of 100: worst 5 outcomes contain 4 losses and 1 zero.
    assert es([100] * 4 + [0] * 96, .95) == pytest.approx(80)
    # Worst 1% of 250 outcomes includes half of the third-largest loss.
    assert es([10, 8, 4] + [0] * 247, .99) == pytest.approx(8)
    assert es([7] * 100, .975) == pytest.approx(7)


def test_missing_quote_does_not_redistribute_capital():
    dates = pd.date_range("2020-01-31", periods=2, freq="ME")
    weights = pd.DataFrame([[.5, .5]] * 2, index=dates)
    returns = pd.DataFrame([[0, 0], [.10, np.nan]], index=dates)
    hold = example_function("16-momentum.qmd", "hold", ret=returns)
    assert hold(weights).iloc[0] == pytest.approx(.05)


def test_stale_quote_cannot_enter_new_portfolio():
    dates = pd.date_range("2020-01-31", periods=1, freq="ME")
    signal = pd.DataFrame([[.9, .2, .1]], index=dates)
    liquid = pd.DataFrame([[10., 10., 10.]], index=dates)
    available = pd.DataFrame([[False, True, True]], index=dates)
    sort = example_function("16-momentum.qmd", "sort_portfolios",
                            available=available, liq=liquid)
    winners, losers = sort(signal, q=.5, drop_liq=0, min_n=2)
    assert winners.iloc[0].tolist() == [0., 1., 0.]
    assert losers.iloc[0].tolist() == [0., 0., 1.]


def test_cohort_weights_drift_with_prices():
    dates = pd.date_range("2020-01-31", periods=3, freq="ME")
    weights = pd.DataFrame([[.5, .5]] * 3, index=dates)
    returns = pd.DataFrame([[0, 0], [1, 0], [1, 0]], index=dates)
    hold = example_function("16-momentum.qmd", "hold", ret=returns)
    # Old cohort has weights 2/3,1/3; new cohort has 1/2,1/2.
    assert hold(weights, K=2).iloc[-1] == pytest.approx((2/3 + 1/2) / 2)


def test_roll_uses_paired_covariance():
    roll = example_function("17-microstructure.qmd", "roll")
    # Lagged vectors [3,2,1] and [0,3,2] have covariance -1.
    assert roll(pd.Series([0., 3., 2., 1.])) == pytest.approx(20000)


def test_irr_bracket_can_include_rates_above_one():
    npv = example_function("appendix-python.qmd", "npv")
    irr = example_function("appendix-python.qmd", "irr", npv=npv, brentq=brentq)
    assert irr([-100, 250], upper=2) == pytest.approx(1.5)
    with pytest.raises(ValueError):
        irr([-100, 250], lower=-1)

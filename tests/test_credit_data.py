"""Checks of the chapter 14 snapshot: integrity, no licensed identifiers, basic consistency.

Run: python -m pytest tests/test_credit_data.py
"""
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qf import data  # noqa: E402

from test_book_methods import example_function  # noqa: E402

CREDIT = ROOT / "data" / "credit"
AGGREGATES = [n for n in data.CREDIT_FILES if n != "cross_section"]


def test_snapshot_hashes_and_file_list():
    meta = data.verify_credit_snapshot()
    on_disk = {p.name for p in CREDIT.glob("*.parquet")}
    assert on_disk == set(meta["files"]) == {f"{n}.parquet" for n in data.CREDIT_FILES}


@pytest.mark.parametrize("name", AGGREGATES)
def test_aggregates_have_no_identifiers(name):
    df = data.load_credit(name)
    banned = {"isin", "secid", "issuer", "emitter", "paper", "name", "regnumber", "inn"}
    assert not banned & {c.lower() for c in df.columns}
    isin = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b")
    for col in df.select_dtypes(include="object"):
        assert not df[col].astype(str).str.contains(isin).any(), col


def test_small_cells_hide_amounts():
    ev = data.load_credit("default_events")
    assert ev.loc[ev["issuers"] < 3, "unpaid_mln"].isna().all()


def test_cohort_counts_consistent():
    r = data.load_credit("default_rates")
    total = r[r["size"] == "все"].set_index("year")
    parts = r[r["size"] != "все"].groupby("year")[["issuers", "defaults"]].sum()
    pd.testing.assert_frame_equal(total[["issuers", "defaults"]], parts, check_dtype=False)
    assert (r["defaults"] <= r["issuers"]).all()


def test_spread_buckets_monotone_for_fixed_coupon():
    sb = data.load_credit("spread_buckets")
    fx = sb[sb["sample"] == "fixed"]
    freq = (fx["defaults"] / fx["obs"]).to_numpy()
    assert freq[-1] > freq[2] > freq[0] - 1e-12


def test_wilson_interval_matches_reference():
    wilson = example_function("14-credit-risk.qmd", "wilson")
    low, high = wilson(np.array([5]), np.array([100]))
    # Wilson 95% interval for 5/100: 0.0215–0.1118
    assert low[0] == pytest.approx(0.02154, abs=1e-4)
    assert high[0] == pytest.approx(0.11175, abs=1e-4)


def test_cross_section_gspread_close_to_parametric_curve():
    xs = data.load_credit("cross_section")
    curve = data.load_zcyc(start=xs["date"].iloc[0], end=xs["date"].iloc[0])
    assert len(curve) >= 10
    g = 100 * (xs["ytm_pct"] - np.interp(xs["duration_days"] / 365, curve["period"], curve["value"]))
    assert g.notna().all() and len(g) > 300

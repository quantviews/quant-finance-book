"""Offline checks: book readers need neither moexutils nor the analytics package."""

from pathlib import Path

import numpy as np

from qf import bonds, data


def test_frozen_snapshot_and_standalone_module_are_consistent():
    meta = data.verify_bond_snapshot()
    assert len(meta["secids"]) == 4
    assert meta["valuation_date"] == "2026-09-30"
    assert "moexutils" not in Path(bonds.__file__).read_text(encoding="utf-8")


def test_every_example_reprices_and_has_single_principal_payment():
    meta = data.verify_bond_snapshot()
    day = bonds.as_date(meta["valuation_date"])
    for ticker in meta["secids"]:
        quote = data.load_bonds(ticker, start=day, end=day).iloc[0]
        coupons = data.load_bond_coupons(ticker, start=day)
        principal = data.load_bond_principal(ticker, start=day)
        flows = [
            bonds.CashFlow(row.payment_date.date(), row.amount)
            for row in list(coupons.itertuples()) + list(principal.itertuples())
        ]
        assert len(principal) == 1
        assert principal["amount"].sum() == quote.face_value
        price = bonds.dirty_price_from_quote(
            quote.clean_pct, quote.face_value, quote.accrued
        )
        y = bonds.yield_to_maturity(flows, day, price)
        assert np.isclose(bonds.price_from_yield(flows, day, y), price, rtol=1e-10)

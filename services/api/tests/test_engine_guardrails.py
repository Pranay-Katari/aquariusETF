import numpy as np
import pandas as pd
import pytest

from services.api.app.services.engine import simulate


def config(cost=0):
    return {"initial_capital": 10000, "commission_bps": cost, "slippage_bps": 0, "rebalance_frequency": "monthly", "risk_free_rate": 0}


def test_single_asset_matches_its_price_return_without_costs():
    dates = pd.date_range("2024-01-02", periods=4, freq="B")
    prices = pd.DataFrame({"SPY": [100, 101, 103, 105]}, index=dates)
    result = simulate(prices, prices["SPY"], [{"ticker": "SPY", "target_weight": 1}], config())
    assert result["metrics"]["ending_value"] == pytest.approx(10500)
    assert result["metrics"]["max_drawdown"] <= 0


def test_costs_never_improve_ending_value_and_weights_must_sum_to_one():
    dates = pd.date_range("2024-01-02", periods=35, freq="B")
    prices = pd.DataFrame({"SPY": np.linspace(100, 110, len(dates)), "QQQ": np.linspace(100, 120, len(dates))}, index=dates)
    holdings = [{"ticker": "SPY", "target_weight": .5}, {"ticker": "QQQ", "target_weight": .5}]
    free = simulate(prices, prices["SPY"], holdings, config())
    costly = simulate(prices, prices["SPY"], holdings, config(25))
    assert costly["metrics"]["ending_value"] <= free["metrics"]["ending_value"]
    with pytest.raises(ValueError, match="fully allocated"):
        simulate(prices, prices["SPY"], [{"ticker": "SPY", "target_weight": .9}], config())

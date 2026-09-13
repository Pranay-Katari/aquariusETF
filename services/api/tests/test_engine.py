from datetime import date
import numpy as np
import pandas as pd
import pytest
from services.api.app.services.engine import simulate, metrics

DATES = [date(2024, 1, 30), date(2024, 1, 31), date(2024, 2, 1), date(2024, 2, 2)]
CFG = {
    "initial_capital": 10000,
    "commission_bps": 0,
    "slippage_bps": 0,
    "rebalance_frequency": "none",
    "risk_free_rate": 0,
}
HOLDINGS = [
    {"ticker": "A", "target_weight": 0.5},
    {"ticker": "B", "target_weight": 0.5},
]


def toy(config=None):
    prices = pd.DataFrame(
        {"A": [100, 110, 120, 108], "B": [100, 90, 80, 88]}, index=DATES
    )
    return simulate(
        prices,
        pd.Series([100, 101, 102, 103], index=DATES),
        HOLDINGS,
        {**CFG, **(config or {})},
    )


def test_hand_computable_buy_and_hold():
    result = toy()
    assert [r["portfolio_nav"] for r in result["series"]] == pytest.approx(
        [10000, 10000, 10000, 9800]
    )
    assert result["metrics"]["total_return"] == pytest.approx(-0.02)
    assert {a["ticker"]: a["pnl"] for a in result["attribution"]} == pytest.approx(
        {"A": 400, "B": -600}
    )
    assert result["metrics"]["max_drawdown"] == pytest.approx(-0.02)


def test_monthly_rebalance():
    r = toy({"rebalance_frequency": "monthly"})
    assert [v["portfolio_nav"] for v in r["series"]] == pytest.approx([10000] * 4)
    assert len(r["rebalances"]) == 2
    assert r["rebalances"][1]["trades"][0]["notional"] == pytest.approx(-1000)
    assert r["rebalances"][1]["trades"][1]["notional"] == pytest.approx(1000)
    assert r["metrics"]["turnover"] == pytest.approx(0.1)


def test_costs_self_finance_and_attribution_reconciles():
    r = toy({"rebalance_frequency": "monthly", "commission_bps": 10, "slippage_bps": 5})
    assert r["series"][0]["portfolio_nav"] == pytest.approx(10000 / 1.0015)
    assert all(v["cash"] >= 0 for v in r["holdings_history"])
    assert sum(a["contribution_to_return"] for a in r["attribution"]) == pytest.approx(
        r["metrics"]["total_return"]
    )
    assert r["metrics"]["total_costs"] == pytest.approx(
        sum(e["costs"] for e in r["rebalances"])
    )


def test_single_stock_matches_benchmark():
    p = pd.Series([100, 120, 90, 130], index=DATES)
    r = simulate(
        pd.DataFrame({"SPY": p}), p, [{"ticker": "SPY", "target_weight": 1}], CFG
    )
    assert [v["portfolio_nav"] for v in r["series"]] == pytest.approx(
        [v["benchmark_nav"] for v in r["series"]]
    )
    assert r["metrics"]["beta"] == pytest.approx(1)
    assert r["metrics"]["tracking_error"] == pytest.approx(0)
    assert r["metrics"]["alpha"] == pytest.approx(0)
    assert r["metrics"]["max_drawdown"] == pytest.approx(-0.25)


def test_missing_prices_fail():
    with pytest.raises(ValueError, match="Missing"):
        simulate(
            pd.DataFrame({"A": [100, np.nan, 110, 120], "B": [100] * 4}, index=DATES),
            pd.Series([100] * 4, index=DATES),
            HOLDINGS,
            CFG,
        )


def test_zero_volatility_null_ratios():
    p = pd.Series([100] * 4, index=DATES)
    r = simulate(pd.DataFrame({"A": p}), p, [{"ticker": "A", "target_weight": 1}], CFG)
    assert r["metrics"]["sharpe"] is None
    assert r["metrics"]["sortino"] is None
    assert r["metrics"]["beta"] is None


def test_cagr_calendar_days():
    r = metrics([100, 110], [100, 105], [date(2023, 1, 1), date(2024, 1, 1)], 100)
    assert r["cagr"] == pytest.approx(1.1 ** (365.25 / 365) - 1)


@pytest.mark.parametrize(
    "frequency,events", [("none", 1), ("monthly", 4), ("quarterly", 2)]
)
def test_rebalance_calendar(frequency, events):
    dates = [date(2024, 1, 2), date(2024, 2, 1), date(2024, 3, 1), date(2024, 4, 1)]
    p = pd.Series([100, 110, 100, 120], index=dates)
    r = simulate(
        pd.DataFrame({"A": p}),
        p,
        [{"ticker": "A", "target_weight": 1}],
        {**CFG, "rebalance_frequency": frequency},
    )
    assert len(r["rebalances"]) == events


def test_initial_fees_count_in_drawdown():
    p = pd.Series([100] * 4, index=DATES)
    r = simulate(
        pd.DataFrame({"A": p}),
        p,
        [{"ticker": "A", "target_weight": 1}],
        {**CFG, "commission_bps": 100},
    )
    assert r["metrics"]["max_drawdown"] == pytest.approx(1 / 1.01 - 1)

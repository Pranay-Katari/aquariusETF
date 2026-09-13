"""Deterministic fractional-share simulation with self-financing transaction costs."""

import hashlib
import json
import numpy as np
import pandas as pd

ENGINE_VERSION = "1.0.0"


def metrics(nav, benchmark, dates, initial_capital, risk_free_rate=0):
    nav = np.asarray(nav, dtype=float)
    bench = np.asarray(benchmark, dtype=float)
    r = nav[1:] / nav[:-1] - 1
    b = bench[1:] / bench[:-1] - 1
    days = (dates[-1] - dates[0]).days
    total = nav[-1] / initial_capital - 1
    cagr = (nav[-1] / initial_capital) ** (365.25 / days) - 1 if days else None
    vol = float(np.std(r, ddof=1) * np.sqrt(252)) if len(r) > 1 else 0.0
    annual = float(np.mean(r) * 252)
    ba = float(np.mean(b) * 252)
    downside = float(
        np.sqrt(np.mean(np.minimum(r - risk_free_rate / 252, 0) ** 2)) * np.sqrt(252)
    )
    beta = (
        float(np.cov(r, b, ddof=1)[0, 1] / np.var(b, ddof=1))
        if len(r) > 1 and np.var(b) > 1e-20
        else None
    )
    peaks = np.maximum.accumulate(np.r_[initial_capital, nav])[1:]
    return {
        "ending_value": float(nav[-1]),
        "total_return": float(total),
        "cagr": float(cagr) if cagr is not None else None,
        "annualized_volatility": vol,
        "sharpe": (annual - risk_free_rate) / vol if vol > 1e-12 else None,
        "sortino": (annual - risk_free_rate) / downside if downside > 1e-12 else None,
        "max_drawdown": float(np.min(nav / peaks - 1)),
        "beta": beta,
        "alpha": annual - (risk_free_rate + beta * (ba - risk_free_rate))
        if beta is not None
        else None,
        "tracking_error": float(np.std(r - b, ddof=1) * np.sqrt(252))
        if len(r) > 1
        else None,
        "win_rate": float(np.mean(r > 0)),
        "best_day": float(max(r)),
        "worst_day": float(min(r)),
        "benchmark_return": float(bench[-1] / initial_capital - 1),
    }


def simulate(
    prices: pd.DataFrame, benchmark: pd.Series, holdings: list[dict], config: dict
):
    tickers = [h["ticker"] for h in holdings if h["target_weight"] > 0]
    weights = np.array(
        [h["target_weight"] for h in holdings if h["target_weight"] > 0], dtype=float
    )
    if not len(tickers) or abs(sum(weights) - 1) > 1e-6:
        raise ValueError("Portfolio must be fully allocated")
    aligned = (
        prices[tickers].join(benchmark.rename("__benchmark"), how="outer").sort_index()
    )
    if len(aligned) < 2:
        raise ValueError("At least two trading sessions are required")
    if aligned.isna().any().any():
        raise ValueError(
            "Missing constituent or benchmark bars; choose a common history. Prices are never forward-filled."
        )
    if not np.isfinite(aligned.to_numpy()).all() or (aligned <= 0).any().any():
        raise ValueError("Prices must be positive and finite")
    dates = list(aligned.index)
    p = aligned[tickers].to_numpy()
    bp = aligned["__benchmark"].to_numpy()
    capital = float(config["initial_capital"])
    rate = (config["commission_bps"] + config["slippage_bps"]) / 10000
    frequency = config["rebalance_frequency"]
    shares = np.zeros(len(tickers))
    cash = capital
    nav = []
    events = []
    contribution = np.zeros(len(tickers))
    cost_by_stock = np.zeros(len(tickers))
    weight_history = []
    traded = np.zeros(len(tickers))
    holdings_history = []
    for i, dt in enumerate(dates):
        if i:
            contribution += shares * (p[i] - p[i - 1])
        before = shares * p[i]
        value = float(cash + sum(before))
        rebalance = (
            i == 0
            or (
                frequency == "monthly"
                and (dt.year, dt.month) != (dates[i - 1].year, dates[i - 1].month)
            )
            or (
                frequency == "quarterly"
                and (dt.year, (dt.month - 1) // 3)
                != (dates[i - 1].year, (dates[i - 1].month - 1) // 3)
            )
        )
        if rebalance:
            # Solve x + cost(sum(abs(x*w - current_exposure))) = pretrade NAV.
            lo, hi = 0.0, value
            for _ in range(80):
                mid = (lo + hi) / 2
                if mid + rate * np.abs(mid * weights - before).sum() > value:
                    hi = mid
                else:
                    lo = mid
            target = (lo + hi) / 2 * weights
            trades = target - before
            costs = np.abs(trades) * rate
            shares = target / p[i]
            cash = value - float(sum(target)) - float(sum(costs))
            if cash < -1e-7:
                raise ValueError("Negative cash accounting error")
            cash = max(cash, 0.0)
            cost_by_stock += costs
            traded += np.abs(trades)
            events.append(
                {
                    "time": str(dt),
                    "initial": i == 0,
                    "costs": float(sum(costs)),
                    "before_weights": dict(zip(tickers, (before / value).tolist())),
                    "after_weights": dict(zip(tickers, weights.tolist())),
                    "trades": [
                        {"ticker": t, "notional": float(n), "cost": float(c)}
                        for t, n, c in zip(tickers, trades, costs)
                    ],
                }
            )
        current = shares * p[i]
        value = float(cash + sum(current))
        nav.append(value)
        weight_history.append(current / value)
        holdings_history.append(
            {
                "time": str(dt),
                "shares": dict(zip(tickers, shares.tolist())),
                "cash": cash,
            }
        )
    bench = capital * bp / bp[0]
    output_metrics = metrics(
        nav, bench, dates, capital, config.get("risk_free_rate", 0)
    )
    # One-way turnover excludes the initial allocation; denominator is mean NAV.
    rebalance_notional = sum(
        abs(t["notional"]) for e in events if not e["initial"] for t in e["trades"]
    )
    output_metrics.update(
        {
            "turnover": rebalance_notional / (2 * np.mean(nav)),
            "total_costs": float(sum(cost_by_stock)),
        }
    )
    peaks = np.maximum.accumulate(np.r_[capital, nav])[1:]
    series = [
        {
            "time": str(dt),
            "portfolio_nav": float(n),
            "benchmark_nav": float(b),
            "portfolio_return": float(n / capital - 1),
            "drawdown": float(n / peak - 1),
        }
        for dt, n, b, peak in zip(dates, nav, bench, peaks)
    ]
    attribution = [
        {
            "ticker": t,
            "contribution_to_return": float((gain - cost) / capital),
            "pnl": float(gain - cost),
            "average_weight": float(np.mean(weight_history, axis=0)[j]),
            "current_weight": float(weight_history[-1][j]),
            "traded_notional": float(traded[j]),
        }
        for j, (t, gain, cost) in enumerate(zip(tickers, contribution, cost_by_stock))
    ]
    return {
        "metrics": output_metrics,
        "series": series,
        "attribution": attribution,
        "rebalances": events,
        "holdings_history": holdings_history,
        "metadata": {
            "engine_version": ENGINE_VERSION,
            "config": config,
            "holdings": holdings,
            "actual_start": str(dates[0]),
            "actual_end": str(dates[-1]),
            "classification": "Retrospective basket backtest",
            "execution": "First session adjusted close; rebalance at first session close of each new period. Fixed ex-ante weights; fractional synthetic units.",
            "dividends": "Adjusted-close total return; no separate dividend or split credits.",
            "metrics_convention": "252 sessions/year; sample volatility; Sharpe and alpha use arithmetic annualized daily returns; CAGR uses elapsed calendar days; undefined ratios are null.",
            "turnover_convention": "Half of absolute rebalance notional / mean NAV; initial allocation excluded.",
        },
    }


def canonical_hash(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()

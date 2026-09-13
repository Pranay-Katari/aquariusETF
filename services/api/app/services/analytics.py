"""Derived analysis uses only persisted daily results, never new price queries."""

from datetime import date


def diagnostics(artifact):
    rows = artifact["series"]
    cfg = artifact["metadata"]["config"]
    episodes = []
    peak = cfg["initial_capital"]
    peak_date = rows[0]["time"]
    current = None
    for row in rows:
        value = row["portfolio_nav"]
        dt = row["time"]
        if value >= peak:
            if current:
                current["recovery"] = dt
                current["duration_days"] = (
                    date.fromisoformat(dt) - date.fromisoformat(current["peak"])
                ).days
                episodes.append(current)
                current = None
            peak = value
            peak_date = dt
        elif current is None:
            current = {
                "peak": peak_date,
                "trough": dt,
                "depth": value / peak - 1,
                "recovery": None,
                "duration_days": None,
            }
        elif value / peak - 1 < current["depth"]:
            current["trough"] = dt
            current["depth"] = value / peak - 1
    if current:
        current["duration_days"] = (
            date.fromisoformat(rows[-1]["time"]) - date.fromisoformat(current["peak"])
        ).days
        episodes.append(current)
    rolling = []
    for i, row in enumerate(rows):
        if i < 21:
            continue
        rolling.append(
            {
                "time": row["time"],
                "portfolio": row["portfolio_nav"] / rows[i - 21]["portfolio_nav"] - 1,
                "benchmark": row["benchmark_nav"] / rows[i - 21]["benchmark_nav"] - 1,
            }
        )
    return {
        "rebalances": artifact["rebalances"],
        "drawdowns": sorted(episodes, key=lambda e: e["depth"])[:10],
        "rolling_21_session_returns": rolling,
        "current_weights": [
            {"ticker": a["ticker"], "weight": a["current_weight"]}
            for a in artifact["attribution"]
        ],
        "metadata": artifact["metadata"],
    }

from services.api.app.services.analytics import diagnostics


def test_drawdown_recovery_and_open_episode():
    rows = [
        {"time": d, "portfolio_nav": v, "benchmark_nav": 100}
        for d, v in [
            ("2024-01-02", 100),
            ("2024-01-03", 90),
            ("2024-01-04", 80),
            ("2024-01-05", 100),
            ("2024-01-08", 95),
        ]
    ]
    d = diagnostics(
        {
            "series": rows,
            "metadata": {"config": {"initial_capital": 100}},
            "rebalances": [],
            "attribution": [],
        }
    )
    assert d["drawdowns"][0]["trough"] == "2024-01-04"
    assert d["drawdowns"][0]["recovery"] == "2024-01-05"
    assert d["drawdowns"][1]["recovery"] is None
    assert d["rolling_21_session_returns"] == []

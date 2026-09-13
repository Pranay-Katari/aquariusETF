from datetime import date
import pytest
from services.api.app.services.market import MarketService, sessions
from services.api.app.config import settings
from services.api.app.services.broker import size_orders


class FakeCache:
    def __init__(self):
        self.data = {}
        self.expirations = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, ex):
        self.data[key] = value
        self.expirations[key] = ex


def test_calendar_holidays():
    assert sessions(date(2024, 7, 3), date(2024, 7, 5)) == [
        date(2024, 7, 3),
        date(2024, 7, 5),
    ]


def test_durable_cache_and_redis(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    service = MarketService()
    service.cache = FakeCache()
    first = service.prices("NVDA", date(2024, 1, 2), date(2024, 2, 1))
    monkeypatch.setattr(
        service.provider,
        "get_bars",
        lambda *args: pytest.fail("Provider should not be called"),
    )
    second = service.prices("NVDA", date(2024, 1, 2), date(2024, 2, 1))
    assert first.tolist() == second.tolist()
    assert service.hits == 1
    assert list(service.cache.expirations.values()) == [3600]
    service.cache.data.clear()  # Expiration / flush must fall back to Parquet.
    third = service.prices("NVDA", date(2024, 1, 2), date(2024, 2, 1))
    assert first.tolist() == third.tolist()


def test_synthetic_range_independence(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    s = MarketService()
    small = s.provider.get_bars("NVDA", date(2024, 2, 1), date(2024, 3, 1))
    big = s.provider.get_bars("NVDA", date(2024, 1, 1), date(2024, 4, 1))
    assert (
        small.adjusted_close.tolist()
        == big[big.date.isin(small.date)].adjusted_close.tolist()
    )


def test_paper_rounding_and_idempotency():
    holdings = [
        {"ticker": "A", "target_weight": 1 / 3},
        {"ticker": "B", "target_weight": 2 / 3},
    ]
    orders, residual = size_orders(holdings, 100, "preview-1")
    assert [o["notional"] for o in orders] == ["33.33", "66.66"]
    assert residual == pytest.approx(0.01)
    assert size_orders(holdings, 100, "preview-1")[0] == orders
    assert (
        size_orders(holdings, 100, "preview-2")[0][0]["client_order_id"]
        != orders[0]["client_order_id"]
    )


def test_market_rejects_untrusted_symbol_paths(tmp_path, monkeypatch):
    from services.api.app.services.market import MarketError

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    service = MarketService()
    assert service.validate_symbol("../NVDA") is False
    with pytest.raises(MarketError, match="Invalid ticker"):
        service.prices("../NVDA", date(2024, 1, 2), date(2024, 2, 1))

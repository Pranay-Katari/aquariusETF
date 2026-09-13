"""Provider-neutral daily total-return prices. No silent data substitutions."""

import hashlib
import json
import logging
import re
import threading
import time
from datetime import date, datetime, timezone, timedelta
from functools import lru_cache
import httpx
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import redis
from ..config import settings
from .storage import storage

CATALOG = {
    "NVDA": (
        "NVIDIA",
        "Accelerated computing",
        "https://www.nvidia.com/en-us/data-center/",
        "GPUs and accelerated computing platforms for data centers.",
    ),
    "AVGO": (
        "Broadcom",
        "Semiconductors",
        "https://www.broadcom.com/products",
        "Networking and custom silicon infrastructure.",
    ),
    "VRT": (
        "Vertiv",
        "Power & cooling",
        "https://www.vertiv.com/en-us/solutions/",
        "Critical power and thermal management for data centers.",
    ),
    "ANET": (
        "Arista Networks",
        "Networking",
        "https://www.arista.com/en/solutions",
        "Cloud networking and data center switching.",
    ),
    "MSFT": (
        "Microsoft",
        "Cloud platforms",
        "https://azure.microsoft.com/en-us/solutions/ai",
        "Azure cloud infrastructure and AI services.",
    ),
    "AMZN": (
        "Amazon",
        "Cloud platforms",
        "https://aws.amazon.com/ai/",
        "Cloud compute and AI infrastructure through AWS.",
    ),
    "GOOGL": (
        "Alphabet",
        "Cloud platforms",
        "https://cloud.google.com/solutions/ai",
        "Cloud AI services and computing infrastructure.",
    ),
    "AMD": (
        "Advanced Micro Devices",
        "Semiconductors",
        "https://www.amd.com/en/products/accelerators.html",
        "Data center processors and compute accelerators.",
    ),
    "TSM": (
        "Taiwan Semiconductor",
        "Foundry",
        "https://www.tsmc.com/english",
        "Semiconductor manufacturing and advanced packaging.",
    ),
    "ASML": (
        "ASML",
        "Chip equipment",
        "https://www.asml.com/en/products",
        "Lithography equipment for semiconductor production.",
    ),
    "AAPL": (
        "Apple",
        "Consumer technology",
        "https://www.apple.com/",
        "Consumer hardware, software and services.",
    ),
    "META": (
        "Meta Platforms",
        "Digital platforms",
        "https://about.meta.com/",
        "Social platforms and AI infrastructure.",
    ),
    "TSLA": (
        "Tesla",
        "Electrification",
        "https://www.tesla.com/energy",
        "Electric vehicles, battery storage and energy products.",
    ),
    "NEE": (
        "NextEra Energy",
        "Clean energy",
        "https://www.nexteraenergy.com/",
        "Renewable generation and electric utility operations.",
    ),
    "FSLR": (
        "First Solar",
        "Clean energy",
        "https://www.firstsolar.com/",
        "Thin-film photovoltaic solar modules.",
    ),
    "ENPH": (
        "Enphase Energy",
        "Clean energy",
        "https://enphase.com/",
        "Solar microinverters and residential battery systems.",
    ),
    "BEPC": (
        "Brookfield Renewable",
        "Clean energy",
        "https://bep.brookfield.com/",
        "Renewable power assets across multiple technologies.",
    ),
    "ISRG": (
        "Intuitive Surgical",
        "Healthcare",
        "https://www.intuitive.com/",
        "Robotic surgical systems.",
    ),
    "UNH": (
        "UnitedHealth Group",
        "Healthcare",
        "https://www.unitedhealthgroup.com/",
        "Health benefits and care delivery services.",
    ),
    "LLY": (
        "Eli Lilly",
        "Healthcare",
        "https://www.lilly.com/",
        "Pharmaceutical research and medicines.",
    ),
    "JNJ": (
        "Johnson & Johnson",
        "Healthcare",
        "https://www.jnj.com/",
        "Innovative medicine and medical technology.",
    ),
    "SPY": (
        "SPDR S&P 500 ETF",
        "Benchmark",
        "https://www.ssga.com/us/en/individual/etfs/spdr-sp-500-etf-trust-spy",
        "Broad US equity benchmark.",
    ),
    "QQQ": (
        "Invesco QQQ",
        "Benchmark",
        "https://www.invesco.com/qqq-etf/en/home.html",
        "Nasdaq-100 benchmark.",
    ),
}


@lru_cache(maxsize=128)
def sessions(start: date, end: date):
    return [
        v.date()
        for v in mcal.get_calendar("NYSE").valid_days(start_date=start, end_date=end)
    ]


class MarketError(ValueError):
    pass


class SyntheticProvider:
    name = "synthetic-v1"

    def validate_symbol(self, symbol):
        return symbol in CATALOG

    def get_bars(self, symbol, start, end):
        if not self.validate_symbol(symbol):
            raise MarketError(f"{symbol} is unavailable in the demo catalog")
        dates = sessions(date(2000, 1, 1), date.today())
        seed = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
        market = np.random.default_rng(42).normal(0.00028, 0.009, len(dates))
        noise = np.random.default_rng(seed).normal(
            0, 0.004 if symbol in ("SPY", "QQQ") else 0.012, len(dates)
        )
        prices = 100 * np.exp(
            np.cumsum(market * (0.9 + (seed % 8) / 10) + noise + 0.00005)
        )
        return pd.DataFrame({"date": dates, "adjusted_close": prices}).query(
            "date >= @start and date <= @end"
        )


class AlphaVantageProvider:
    name = "alphavantage-adjusted-v1"

    def validate_symbol(self, symbol):
        return not self.get_bars(symbol, date.today(), date.today()).empty

    def get_bars(self, symbol, start, end):
        if not settings.market_data_api_key:
            raise MarketError("MARKET_DATA_API_KEY is required for Alpha Vantage")
        try:
            response = httpx.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "TIME_SERIES_DAILY_ADJUSTED",
                    "symbol": symbol,
                    "outputsize": "full",
                    "apikey": settings.market_data_api_key,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketError("Market provider request failed; retry later") from exc
        raw = data.get("Time Series (Daily)")
        if not raw:
            raise MarketError(
                f"No adjusted history for {symbol}. Check symbol, API entitlement and provider rate limits."
            )
        # Return full history for durable reuse. Adjusted close embeds splits and dividends.
        rows = [
            {
                "date": date.fromisoformat(d),
                "open": float(v["1. open"]),
                "high": float(v["2. high"]),
                "low": float(v["3. low"]),
                "close": float(v["4. close"]),
                "adjusted_close": float(v["5. adjusted close"]),
                "volume": int(v["6. volume"]),
            }
            for d, v in raw.items()
        ]
        return pd.DataFrame(rows).sort_values("date")


class MarketService:
    def __init__(self):
        if settings.market_data_provider not in ("synthetic", "alphavantage"):
            raise ValueError("Unknown market data provider")
        self.provider = (
            SyntheticProvider()
            if settings.market_data_provider == "synthetic"
            else AlphaVantageProvider()
        )
        self.cache = (
            redis.Redis.from_url(
                settings.redis_url, socket_connect_timeout=1, socket_timeout=1
            )
            if settings.redis_url
            else None
        )
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.root = settings.data_dir / "market" / self.provider.name
        self.root.mkdir(parents=True, exist_ok=True)

    def validate_symbol(self, symbol):
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol):
            return False
        if isinstance(self.provider, SyntheticProvider):
            return symbol in CATALOG
        try:
            recent = self.prices(
                symbol, date.today() - timedelta(days=30), date.today()
            )
            return not recent.empty and (date.today() - recent.index[-1]).days <= 7
        except MarketError:
            return False

    def prices(self, symbol, start, end):
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,9}", symbol):
            raise MarketError("Invalid ticker")
        key = f"bars:{self.provider.name}:{symbol}:1d:{start}:{end}"
        with self.lock:
            if self.cache:
                try:
                    cached = self.cache.get(key)
                    if cached:
                        self.hits += 1
                        rows = json.loads(cached)
                        return pd.Series(
                            [r[1] for r in rows],
                            index=[date.fromisoformat(r[0]) for r in rows],
                            name=symbol,
                        )
                except redis.RedisError:
                    logging.getLogger(__name__).warning("redis_unavailable")
            self.misses += 1
            path = self.root / f"{symbol}.parquet"
            object_key = f"market/{self.provider.name}/{symbol}.parquet"
            if not path.exists():
                storage.restore(object_key, path)
            df = pd.read_parquet(path) if path.exists() else pd.DataFrame()
            expected = set(sessions(start, end))
            available = set(df["date"]) if not df.empty else set()
            stale = (
                isinstance(self.provider, AlphaVantageProvider)
                and path.exists()
                and time.time() - path.stat().st_mtime > 86400
            )
            if not expected.issubset(available) or stale:
                fresh = self.provider.get_bars(symbol, start, end)
                df = (
                    pd.concat([df, fresh], ignore_index=True)
                    .drop_duplicates("date", keep="last")
                    .sort_values("date")
                )
                if (
                    df.empty
                    or not np.isfinite(df.adjusted_close).all()
                    or (df.adjusted_close <= 0).any()
                ):
                    raise MarketError(f"Invalid prices for {symbol}")
                temp = path.with_suffix(".tmp.parquet")
                df.to_parquet(temp, index=False)
                temp.replace(path)
                storage.upload(object_key, path)
            frame = df[(df.date >= start) & (df.date <= end)] if not df.empty else df
            if frame.empty:
                raise MarketError(f"No history for {symbol} in the requested period")
            result = pd.Series(
                frame.adjusted_close.to_numpy(), index=frame.date, name=symbol
            ).sort_index()
            if self.cache:
                try:
                    self.cache.set(
                        key,
                        json.dumps([[str(d), float(p)] for d, p in result.items()]),
                        ex=3600,
                    )
                except redis.RedisError:
                    pass
            return result

    def provenance(self):
        return {
            "provider": self.provider.name,
            "price_basis": "split-and-dividend-adjusted close",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "synthetic": isinstance(self.provider, SyntheticProvider),
        }


market = MarketService()

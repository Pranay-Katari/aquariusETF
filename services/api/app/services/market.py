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

# Listed proxy instruments let a single daily-price engine model cross-asset themes.
# Spot crypto, futures and physical commodities are deliberately not accepted here.
CATALOG.update({
    "SPY": ("SPDR S&P 500 ETF Trust", "Broad US equities", "https://www.ssga.com/us/en/individual/etfs/spdr-sp-500-etf-trust-spy", "Large-cap US equity benchmark exposure."),
    "QQQ": ("Invesco QQQ Trust", "Nasdaq 100", "https://www.invesco.com/qqq-etf/en/home.html", "Large non-financial Nasdaq companies."),
    "TLT": ("iShares 20+ Year Treasury Bond ETF", "Long Treasury bonds", "https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf", "US long-duration Treasury exposure."),
    "AGG": ("iShares Core U.S. Aggregate Bond ETF", "Aggregate bonds", "https://www.ishares.com/us/products/239458/ishares-core-total-us-bond-market-etf", "Broad investment-grade US bond exposure."),
    "GLD": ("SPDR Gold Shares", "Gold", "https://www.ssga.com/us/en/intermediary/etfs/spdr-gold-shares-gld", "Gold-backed commodity exposure."),
    "SLV": ("iShares Silver Trust", "Silver", "https://www.ishares.com/us/products/239855/ishares-silver-trust-fund", "Silver commodity exposure."),
    "DBC": ("Invesco DB Commodity Index Tracking Fund", "Broad commodities", "https://www.invesco.com/us/financial-products/etfs/product-detail?audienceType=Investor&ticker=DBC", "Diversified commodity futures index exposure."),
    "IBIT": ("iShares Bitcoin Trust ETF", "Bitcoin", "https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf", "Bitcoin exposure through a listed trust."),
    "ETHA": ("iShares Ethereum Trust ETF", "Ethereum", "https://www.ishares.com/us/products/337137/ishares-ethereum-trust-etf", "Ethereum exposure through a listed trust."),
    "VTI": ("Vanguard Total Stock Market ETF", "Broad US equities", "https://investor.vanguard.com/investment-products/etfs/profile/vti", "US total-market equity exposure."),
    "IWM": ("iShares Russell 2000 ETF", "US small caps", "https://www.ishares.com/us/products/239710/ishares-russell-2000-etf", "US small-cap equity exposure."),
    "EFA": ("iShares MSCI EAFE ETF", "Developed international equities", "https://www.ishares.com/us/products/239623/ishares-msci-eafe-etf", "Developed-market equity exposure outside the US and Canada."),
    "EEM": ("iShares MSCI Emerging Markets ETF", "Emerging-market equities", "https://www.ishares.com/us/products/239637/ishares-msci-emerging-markets-etf", "Emerging-market equity exposure."),
    "VNQ": ("Vanguard Real Estate ETF", "US real estate", "https://investor.vanguard.com/investment-products/etfs/profile/vnq", "US listed real-estate investment trust exposure."),
    "XLF": ("Financial Select Sector SPDR Fund", "Financials", "https://www.ssga.com/us/en/intermediary/etfs/funds/the-financial-select-sector-spdr-fund-xlf", "US financial-sector exposure."),
    "XLK": ("Technology Select Sector SPDR Fund", "Technology", "https://www.ssga.com/us/en/intermediary/etfs/funds/the-technology-select-sector-spdr-fund-xlk", "US technology-sector exposure."),
    "XLE": ("Energy Select Sector SPDR Fund", "Energy", "https://www.ssga.com/us/en/intermediary/etfs/funds/the-energy-select-sector-spdr-fund-xle", "US energy-sector exposure."),
    "SOXX": ("iShares Semiconductor ETF", "Semiconductors", "https://www.ishares.com/us/products/239705/ishares-semiconductor-etf", "US listed semiconductor exposure."),
    "SMH": ("VanEck Semiconductor ETF", "Semiconductors", "https://www.vaneck.com/us/en/investments/semiconductor-etf-smh/overview/", "Semiconductor-industry exposure."),
    "ARKK": ("ARK Innovation ETF", "Disruptive innovation", "https://www.ark-funds.com/funds/arkk", "Actively managed disruptive-innovation exposure."),
    "MAGS": ("Roundhill Magnificent Seven ETF", "Mega-cap technology", "https://www.roundhillinvestments.com/etf/mags/", "Equal-weight exposure to the Magnificent Seven companies."),
    "DRAM": ("Roundhill Memory ETF", "Memory semiconductors", "https://www.roundhillinvestments.com/etf/dram/", "Listed exposure to global memory and storage companies."),
    "HUMN": ("Roundhill Humanoid Robotics ETF", "Robotics", "https://www.roundhillinvestments.com/etf/humn/", "Thematic listed exposure to humanoid robotics."),
    "LYTE": ("Roundhill Photonics & Optics ETF", "Photonics", "https://www.roundhillinvestments.com/etf/lyte/", "Thematic listed exposure to photonics and optics."),
    "MARS": ("Roundhill Space & Technology ETF", "Space technology", "https://www.roundhillinvestments.com/etf/mars/", "Thematic listed exposure to space and technology."),
})


@lru_cache(maxsize=128)
def sessions(start: date, end: date):
    return [
        v.date()
        for v in mcal.get_calendar("NYSE").valid_days(start_date=start, end_date=end)
    ]


class MarketError(ValueError):
    pass


from .universe import LISTED_EQUITIES


class SyntheticProvider:
    name = "synthetic-v1"

    def validate_symbol(self, symbol):
        return symbol in CATALOG or symbol in LISTED_EQUITIES

    def get_bars(self, symbol, start, end):
        if not self.validate_symbol(symbol):
            raise MarketError(f"{symbol} is absent from the exchange listing snapshot")
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


class YahooProvider:
    """Daily adjusted closes from Yahoo's chart endpoint for listed symbols."""

    name = "yahoo-adjusted-v1"

    def get_bars(self, symbol, start, end):
        # period2 is exclusive. Add two days to safely include the requested end.
        try:
            response = httpx.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                params={
                    "period1": int(datetime.combine(start, datetime.min.time()).timestamp()),
                    "period2": int(datetime.combine(end + timedelta(days=2), datetime.min.time()).timestamp()),
                    "interval": "1d",
                    "events": "div,splits",
                    "includeAdjustedClose": "true",
                },
                headers={"User-Agent": "AquariusBaskets/1.0 research@example.invalid"},
                timeout=30,
            )
            response.raise_for_status()
            result = response.json().get("chart", {}).get("result", [None])[0]
        except (httpx.HTTPError, ValueError, IndexError) as exc:
            raise MarketError("Yahoo Finance price request failed; retry later") from exc
        if not result or not result.get("timestamp"):
            raise MarketError(f"No listed-market history for {symbol} in the requested period")
        quote = result["indicators"]["quote"][0]
        adjusted = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
        rows = []
        for timestamp, close, adjusted_close, volume in zip(
            result["timestamp"], quote.get("close", []), adjusted, quote.get("volume", [])
        ):
            if adjusted_close is None or adjusted_close <= 0:
                continue
            rows.append(
                {
                    "date": datetime.fromtimestamp(timestamp, timezone.utc).date(),
                    "close": close,
                    "adjusted_close": float(adjusted_close),
                    "volume": int(volume or 0),
                }
            )
        if not rows:
            raise MarketError(f"No usable adjusted-close history for {symbol}")
        return pd.DataFrame(rows).drop_duplicates("date").sort_values("date")


class MarketService:
    def __init__(self):
        if settings.market_data_provider not in ("synthetic", "alphavantage", "yahoo"):
            raise ValueError("Unknown market data provider")
        self.provider = (
            SyntheticProvider()
            if settings.market_data_provider == "synthetic"
            else AlphaVantageProvider()
            if settings.market_data_provider == "alphavantage"
            else YahooProvider()
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
            return symbol in CATALOG or symbol in LISTED_EQUITIES
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
                isinstance(self.provider, (AlphaVantageProvider, YahooProvider))
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

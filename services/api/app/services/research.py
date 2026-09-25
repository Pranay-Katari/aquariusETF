"""Transparent source-backed starter research; no fabricated AI or numerical claims."""

from datetime import datetime, timezone
import math
import re
from .sectors import sector_tickers
from .market import CATALOG, market
from ..schemas import ResearchInput, PortfolioInput

THEMES = {
    "AI infrastructure": (
        [
            "ai",
            "artificial intelligence",
            "data center",
            "datacenter",
            "cloud",
            "infrastructure",
        ],
        ["NVDA", "AVGO", "VRT", "ANET", "MSFT", "AMZN", "GOOGL", "AMD", "TSM", "ASML"],
    ),
    "Semiconductor ecosystem": (
        ["semiconductor", "chip", "silicon"],
        ["NVDA", "AMD", "AVGO", "TSM", "ASML"],
    ),
    "Clean energy": (
        ["clean", "renewable", "solar", "energy", "climate"],
        ["NEE", "FSLR", "ENPH", "BEPC", "TSLA"],
    ),
    "Healthcare innovation": (
        ["health", "medical", "medicine", "surgical"],
        ["ISRG", "LLY", "JNJ", "UNH"],
    ),
    "Technology leaders": (
        ["tech", "digital", "software"],
        ["MSFT", "AAPL", "GOOGL", "META", "AMZN", "NVDA"],
    ),
}


def generate(request: ResearchInput):
    prompt = request.prompt.lower()
    matches = [
        (name, tickers)
        for name, (keywords, tickers) in THEMES.items()
        if any(re.search(r"\b" + re.escape(k) + r"\b", prompt) for k in keywords)
    ]
    if not matches:
        raise ValueError(
            "Starter research supports AI infrastructure, semiconductors, clean energy, healthcare, and technology. Use manual construction for other themes."
        )
    name, tickers = matches[0]
    # Do not silently claim to honor arbitrary constraints in free text.
    if any(
        k in prompt
        for k in ("exclude", "excluding", "without", "minimum", "market cap", "only ")
    ):
        raise ValueError(
            "This starter does not interpret free-text exclusion or fundamental constraints. Build those manually; holding count and maximum weight are enforced below."
        )
    eligible = sector_tickers(request.sector)
    if eligible is not None:
        tickers = [t for t in tickers if t in eligible]
    tickers = tickers[: request.max_holdings]
    if len(tickers) < math.ceil(1 / request.max_weight - 1e-9):
        raise ValueError(
            "Not enough candidates to satisfy the maximum weight. Increase the cap or choose more holdings."
        )
    holdings = []
    warnings = [
        "Curated source-backed starter, not an autonomous AI research run. Company links are references, not historical point-in-time evidence."
    ]
    for ticker in tickers:
        if not market.validate_symbol(ticker):
            raise ValueError(f"Unavailable symbol: {ticker}")
        company, tag, url, rationale = CATALOG[ticker]
        holdings.append(
            {
                "ticker": ticker,
                "company_name": company,
                "target_weight": 1 / len(tickers),
                "theme_tag": tag,
                "rationale": rationale,
                "sources": [
                    {
                        "url": url,
                        "title": f"{company} — company reference",
                        "snippet": rationale,
                    }
                ],
            }
        )
    result = PortfolioInput(
        name=name, symbol="CUSTOM", description=request.prompt, holdings=holdings
    )
    return result, {
        "prompt": request.model_dump(),
        "model": "curated-catalog-v1",
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output": result.model_dump(),
        "validation": {
            "weights_valid": True,
            "symbols_valid": True,
            "max_weight": request.max_weight,
        },
        "warnings": warnings,
    }

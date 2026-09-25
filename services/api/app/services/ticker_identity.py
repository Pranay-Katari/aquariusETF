"""Verified issuer renames; never guess a replacement from a similar ticker."""

from .universe import LISTED_EQUITIES

RENAMES = {
    "ABC": {
        "ticker": "COR",
        "company_name": "Cencora, Inc.",
        "issuer_names": ("amerisourcebergen", "cencora"),
        "effective_date": "2023-08-30",
        "source": "https://www.sec.gov/Archives/edgar/data/1140859/000110465923096698/tm2324358d1_8k.htm",
    },
}


def current_ticker(ticker):
    symbol = ticker.strip().upper()
    rename = RENAMES.get(symbol)
    if rename and symbol not in LISTED_EQUITIES and rename["ticker"] in LISTED_EQUITIES:
        return rename["ticker"]
    return symbol


def resolve_candidate(ticker, company_name):
    symbol = ticker.strip().upper()
    canonical = current_ticker(symbol)
    if canonical == symbol:
        return symbol, company_name, None
    rename = RENAMES[symbol]
    normalized_name = "".join(c for c in company_name.casefold() if c.isalnum())
    if not any(name in normalized_name for name in rename["issuer_names"]):
        raise ValueError(
            f"{symbol} is a retired ticker. Its issuer identity did not match the verified rename, so no replacement was made."
        )
    return (
        canonical,
        rename["company_name"],
        {
            "old_ticker": symbol,
            "ticker": canonical,
            "effective_date": rename["effective_date"],
            "source": rename["source"],
        },
    )

"""Explicit sector classifications for the supported research universe."""

SECTORS = {
    "Technology": {
        "NVDA",
        "AVGO",
        "ANET",
        "MSFT",
        "AMD",
        "TSM",
        "ASML",
        "AAPL",
        "ENPH",
    },
    "Industrials": {"VRT"},
    "Utilities": {"NEE", "BEPC"},
    "Healthcare": {"ISRG", "UNH", "LLY", "JNJ"},
    "Consumer discretionary": {"AMZN", "TSLA"},
    "Communication services": {"GOOGL", "META"},
    "Energy": set(),
}
# First Solar is classified in Information Technology (semiconductor equipment).
SECTORS["Technology"].add("FSLR")


def sector_tickers(sector):
    if not sector:
        return None
    match = next((v for k, v in SECTORS.items() if k.lower() == sector.lower()), None)
    if match is None:
        raise ValueError("Choose a supported sector or select All sectors.")
    return match

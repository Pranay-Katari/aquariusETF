"""Versioned Nasdaq Trader listing snapshot, independent of demo theme seeds."""

import json
from pathlib import Path

SNAPSHOT = json.loads((Path(__file__).parents[1] / "data/us_equities.json").read_text())
LISTED_EQUITIES = SNAPSHOT["symbols"]


def explicit_company_constraints(messages):
    """Preserve explicit include/exclude directives even when the model omits schema fields."""
    import re
    from collections import defaultdict

    aliases = defaultdict(set)
    for ticker, name in LISTED_EQUITIES.items():
        word = re.split(r"[\s,.-]", name)[0]
        if len(word) >= 4:
            aliases[word.casefold()].add(ticker)
    required, excluded = set(), set()
    for message in messages:
        for match in re.finditer(
            r"\b(include|including|add|exclude|excluding|without|remove|drop)\b\s+(.+?)(?=\b(?:include|including|add|exclude|excluding|without|remove|drop)\b|[.;!?]|$)",
            message,
            re.I,
        ):
            clause = match[2]
            tickers = {
                t
                for t in re.findall(r"\b[A-Z][A-Z0-9.-]{0,9}\b", clause)
                if t in LISTED_EQUITIES
            }
            for word in re.findall(r"\b[\w]+\b", clause.casefold()):
                if len(aliases.get(word, ())) == 1:
                    tickers.update(aliases[word])
            if match[1].lower() in ("include", "including", "add"):
                required.update(tickers)
                excluded.difference_update(tickers)
            else:
                excluded.update(tickers)
                required.difference_update(tickers)
    return required, excluded

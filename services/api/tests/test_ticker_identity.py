import json
import pytest
from services.api.app.services.ticker_identity import resolve_candidate, current_ticker
from services.api.app.services import ai_research
from services.api.app.schemas import ResearchInput
from services.api.tests.test_ai_research import responses


def test_verified_rename_requires_issuer_match():
    ticker, name, audit = resolve_candidate("abc", "AmerisourceBergen Corporation")
    assert ticker == "COR" and name == "Cencora, Inc."
    assert audit["source"].startswith("https://www.sec.gov/")
    with pytest.raises(ValueError, match="identity"):
        resolve_candidate("ABC", "Unrelated ABC Software")
    assert current_ticker("ABC") == "COR"
    assert resolve_candidate("UNKNOWN", "Unknown Company") == (
        "UNKNOWN",
        "Unknown Company",
        None,
    )


def test_retired_ticker_proposal_is_validated_as_current_issuer(monkeypatch):
    search, parsed = responses()
    data = json.loads(parsed["output"][0]["content"][0]["text"])
    data["candidates"][0].update(ticker="ABC", company_name="AmerisourceBergen")
    parsed["output"][0]["content"][0]["text"] = json.dumps(data)
    replies = iter([search, parsed])
    monkeypatch.setattr(ai_research, "call_response", lambda _: next(replies))
    p, audit = ai_research.generate_ai(
        ResearchInput(
            prompt="Healthcare companies",
            max_holdings=2,
            max_weight=0.6,
            required_tickers=["ABC"],
        )
    )
    assert p.holdings[0].ticker == "COR"
    assert p.holdings[0].company_name == "Cencora, Inc."
    assert audit["ticker_corrections"][0]["old_ticker"] == "ABC"
    assert sum(h.target_weight for h in p.holdings) == pytest.approx(1)

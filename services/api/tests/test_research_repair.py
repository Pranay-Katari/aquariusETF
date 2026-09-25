import json
import pytest
from services.api.app.services import ai_research
from services.api.app.schemas import ResearchInput
from services.api.tests.test_ai_research import responses


def duplicate_response():
    search, parsed = responses()
    data = json.loads(parsed["output"][0]["content"][0]["text"])
    data["candidates"][0].update(ticker="ABC", company_name="AmerisourceBergen")
    data["candidates"][1].update(ticker="COR", company_name="Cencora")
    parsed["output"][0]["content"][0]["text"] = json.dumps(data)
    return search, parsed


def test_rename_collision_triggers_grounded_repair(monkeypatch):
    replies = iter([*duplicate_response(), *responses()])
    calls = []

    def call(payload):
        calls.append(payload)
        return next(replies)

    monkeypatch.setattr(ai_research, "call_response", call)
    portfolio, audit = ai_research.generate_ai(
        ResearchInput(
            prompt="Pharmaceutical manufacturers and distributors",
            max_holdings=2,
            max_weight=0.6,
        )
    )
    assert len(portfolio.holdings) == len({h.ticker for h in portfolio.holdings}) == 2
    assert sum(h.target_weight for h in portfolio.holdings) == pytest.approx(1)
    assert "COR" in calls[2]["input"] and "previous attempt failed" in calls[2]["input"]
    assert len(audit["automatic_repairs"]) == 1


def test_repair_is_bounded(monkeypatch):
    replies = iter([*duplicate_response(), *duplicate_response()])
    monkeypatch.setattr(ai_research, "call_response", lambda _: next(replies))
    with pytest.raises(ValueError, match="Automatic repair could not"):
        ai_research.generate_ai(
            ResearchInput(
                prompt="Pharmaceutical supply chain", max_holdings=2, max_weight=0.6
            )
        )

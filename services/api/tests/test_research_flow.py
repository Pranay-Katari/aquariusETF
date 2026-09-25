import pytest
from services.api.app.config import settings
from services.api.app.schemas import ResearchChatInput, PortfolioInput
from services.api.app.services import chat, intake
from services.api.app.services.intake import Brief
from services.api.app.services.weights import allocate
from services.api.app.services.market import market
from services.api.app.services.universe import LISTED_EQUITIES


def test_capped_weighting_and_fixed_adjustment():
    w = allocate([9, 3, 2, 1], 0.4)
    assert sum(w) == pytest.approx(1)
    assert max(w) <= 0.4
    assert w[0] > w[-1]
    changed = allocate(w, 0.4, {0: 0.15})
    assert changed[0] == 0.15
    assert sum(changed) == pytest.approx(1)
    assert max(changed) <= 0.4
    with pytest.raises(ValueError):
        allocate([1, 1], 0.4)
    with pytest.raises(ValueError):
        allocate([1, 1, 1], 0.5, {0: 0.7})
    assert allocate([0, 0, 0, 0], 0.25) == [0.25] * 4


def test_ai_clarifies_without_research(monkeypatch):
    monkeypatch.setattr(settings, "research_provider", "openrouter")
    monkeypatch.setattr(
        intake,
        "clarify",
        lambda body: Brief(
            ready=False,
            message="Which part of clean energy: generation, storage, or the grid?",
            theme="Clean energy",
            sector="",
            holdings=12,
            max_weight=0.25,
            weighting="theme",
        ),
    )
    result = chat.respond(ResearchChatInput(messages=["Clean energy"]))
    assert result["proposal"] is None
    assert "storage" in result["message"]


def test_ai_reweight_retains_companies_without_model_call(monkeypatch):
    monkeypatch.setattr(settings, "research_provider", "openrouter")
    monkeypatch.setattr(
        intake,
        "clarify",
        lambda _: pytest.fail("Reweighting should not call the model"),
    )
    portfolio = PortfolioInput(
        name="Chips",
        holdings=[
            {
                "ticker": t,
                "company_name": t,
                "target_weight": 0.25,
                "theme_tag": "Chips",
                "rationale": "Research",
                "sources": [],
            }
            for t in ["NVDA", "AMD", "AVGO", "TSM"]
        ],
    )
    result = chat.respond(
        ResearchChatInput(
            messages=["set NVDA to 15%"], current_proposal=portfolio, max_weight=0.4
        )
    )
    weights = result["proposal"]["holdings"]
    assert weights[0]["target_weight"] == 0.15
    assert sum(h["target_weight"] for h in weights) == pytest.approx(1)
    assert [h["ticker"] for h in weights] == ["NVDA", "AMD", "AVGO", "TSM"]


def test_broad_listing_validation():
    assert len(LISTED_EQUITIES) > 5000
    assert market.validate_symbol("PLTR")
    assert market.validate_symbol("NET")
    assert not market.validate_symbol("FAKESTOCK")
    assert (
        ResearchChatInput(messages=["Grid companies"], max_holdings=40).max_holdings
        == 40
    )


def test_intake_receives_assistant_context(monkeypatch):
    import json

    def response(payload):
        conversation = json.loads(payload["input"])["messages"]
        assert conversation[1]["role"] == "assistant"
        assert "storage" in conversation[1]["text"]
        data = dict(
            ready=True,
            message="Researching grid storage.",
            theme="Grid storage",
            sector="",
            holdings=12,
            max_weight=0.25,
            weighting="theme",
        )
        return {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(data)}],
                }
            ]
        }

    monkeypatch.setattr(intake, "call_response", response)
    result = intake.clarify(
        ResearchChatInput(
            messages=["Clean energy", "storage"],
            history=[
                {"role": "user", "text": "Clean energy"},
                {"role": "assistant", "text": "Generation or storage?"},
                {"role": "user", "text": "storage"},
            ],
        )
    )
    assert result.ready and result.theme == "Grid storage"


def test_named_company_constraints_survive_missing_model_fields():
    from services.api.app.services.universe import explicit_company_constraints

    required, excluded = explicit_company_constraints(
        ["Include Palantir and ServiceNow, exclude NVIDIA."]
    )
    assert {"PLTR", "NOW"} <= required
    assert "NVDA" in excluded
    required, excluded = explicit_company_constraints(
        ["Include PLTR and NOW.", "Remove PLTR."]
    )
    assert required == {"NOW"}
    assert excluded == {"PLTR"}

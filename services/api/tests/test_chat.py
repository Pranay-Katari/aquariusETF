import pytest
from fastapi.testclient import TestClient
from services.api.app.main import app
from services.api.app.auth import _hits
from services.api.app.schemas import ResearchChatInput
from services.api.app.services.chat import respond
from services.api.app.services.sectors import SECTORS


def test_chat_previews_without_saving():
    _hits.clear()
    with TestClient(app) as client:
        before = client.get("/v1/etfs").json()
        r = client.post(
            "/v1/research/chat",
            json={"messages": ["AI infrastructure"], "sector": "Technology"},
        )
        assert r.status_code == 200, r.text
        proposal = r.json()["proposal"]
        assert proposal
        assert {h["ticker"] for h in proposal["holdings"]} <= SECTORS["Technology"]
        assert sum(h["target_weight"] for h in proposal["holdings"]) == pytest.approx(1)
        assert client.get("/v1/etfs").json() == before
        saved = client.post("/v1/etfs", json=proposal)
        assert saved.status_code == 201


def test_followup_retains_theme_and_changes_count():
    r = respond(ResearchChatInput(messages=["AI infrastructure", "Make it 5 holdings"]))
    assert r["proposal"]["name"] == "AI infrastructure"
    assert len(r["proposal"]["holdings"]) == 5


def test_sector_followup_does_not_replace_theme():
    r = respond(
        ResearchChatInput(
            messages=["AI infrastructure", "Focus on the technology sector"]
        )
    )
    assert r["proposal"]["name"] == "AI infrastructure"
    assert r["sector"] == "Technology"
    assert {h["ticker"] for h in r["proposal"]["holdings"]} <= SECTORS["Technology"]


def test_clean_energy_does_not_imply_energy_sector():
    r = respond(ResearchChatInput(messages=["Build a clean energy portfolio"]))
    assert r["sector"] == ""
    assert r["proposal"]


def test_explicit_filter_overrides_old_conversation():
    r = respond(
        ResearchChatInput(
            messages=[
                "AI infrastructure in the technology sector",
                "Make it 8 holdings",
            ],
            sector="",
        )
    )
    assert r["sector"] == ""
    assert len(r["proposal"]["holdings"]) == 8


def test_exclusion_and_infeasible_sector():
    r = respond(ResearchChatInput(messages=["AI infrastructure", "Remove NVDA"]))
    assert all(h["ticker"] != "NVDA" for h in r["proposal"]["holdings"])
    r = respond(ResearchChatInput(messages=["AI infrastructure"], sector="Industrials"))
    assert r["proposal"] is None
    assert "cap" in r["message"]


def test_unknown_theme_and_invalid_constraints_are_explained():
    r = respond(ResearchChatInput(messages=["hello there"]))
    assert r["proposal"] is None
    r = respond(ResearchChatInput(messages=["AI infrastructure", "Make it 100 stocks"]))
    assert r["proposal"] is None
    assert r["max_holdings"] == 8

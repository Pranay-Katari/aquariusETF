import json
import pytest
from services.api.app.schemas import ResearchInput
from services.api.app.services import ai_research

URL = "https://www.nvidia.com/en-us/data-center/"


def responses(candidates=None):
    candidates = candidates or [
        {
            "ticker": "NVDA",
            "company_name": "NVIDIA",
            "subtheme": "Compute",
            "rationale": "Accelerators",
            "confidence": 0.9,
            "source_urls": [URL],
        },
        {
            "ticker": "AMD",
            "company_name": "AMD",
            "subtheme": "Compute",
            "rationale": "Accelerators",
            "confidence": 0.8,
            "source_urls": [URL],
        },
    ]
    search = {
        "id": "search-1",
        "output": [
            {
                "type": "web_search_call",
                "action": {"sources": [{"url": URL, "title": "Company reference"}]},
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "Research evidence"}],
            },
        ],
    }
    parsed = {
        "id": "extract-1",
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "theme": "Compute",
                                "thesis": "AI infrastructure",
                                "candidates": candidates,
                                "warnings": [],
                            }
                        ),
                    }
                ],
            }
        ],
    }
    return search, parsed


def test_grounded_proposal_weights_are_code_computed(monkeypatch):
    reply = iter(responses())
    monkeypatch.setattr(ai_research, "call_response", lambda _: next(reply))
    portfolio, audit = ai_research.generate_ai(
        ResearchInput(prompt="AI infrastructure", max_holdings=2, max_weight=0.5)
    )
    assert sum(h.target_weight for h in portfolio.holdings) == 1
    assert audit["validation"]["sources_resolved"] is True
    assert portfolio.holdings[0].sources[0].url == URL


def test_invented_citation_rejected(monkeypatch):
    search, parsed = responses()
    proposal = json.loads(parsed["output"][0]["content"][0]["text"])
    proposal["candidates"][0]["source_urls"] = ["https://fabricated.example/"]
    parsed["output"][0]["content"][0]["text"] = json.dumps(proposal)
    reply = iter([search, parsed])
    monkeypatch.setattr(ai_research, "call_response", lambda _: next(reply))
    with pytest.raises(ValueError, match="absent from"):
        ai_research.generate_ai(
            ResearchInput(prompt="AI infrastructure", max_holdings=2, max_weight=0.5)
        )


def test_no_source_fails_closed(monkeypatch):
    monkeypatch.setattr(ai_research, "call_response", lambda _: {"output": []})
    with pytest.raises(ValueError, match="no verifiable"):
        ai_research.generate_ai(ResearchInput(prompt="AI infrastructure"))


def test_numbered_sources_resolve_to_actual_urls(monkeypatch):
    search, parsed = responses()
    proposal = json.loads(parsed["output"][0]["content"][0]["text"])
    for candidate in proposal["candidates"]:
        candidate.pop("source_urls")
        candidate["source_ids"] = [0]
    parsed["output"][0]["content"][0]["text"] = json.dumps(proposal)
    reply = iter([search, parsed])
    monkeypatch.setattr(ai_research, "call_response", lambda _: next(reply))
    portfolio, _ = ai_research.generate_ai(
        ResearchInput(prompt="AI infrastructure", max_holdings=2, max_weight=0.6)
    )
    assert all(h.sources[0].url == URL for h in portfolio.holdings)
    assert portfolio.holdings[0].target_weight > portfolio.holdings[1].target_weight


def test_unknown_numbered_source_rejected(monkeypatch):
    search, parsed = responses()
    proposal = json.loads(parsed["output"][0]["content"][0]["text"])
    proposal["candidates"][0].pop("source_urls")
    proposal["candidates"][0]["source_ids"] = [999]
    parsed["output"][0]["content"][0]["text"] = json.dumps(proposal)
    reply = iter([search, parsed])
    monkeypatch.setattr(ai_research, "call_response", lambda _: next(reply))
    with pytest.raises(ValueError, match="unknown source"):
        ai_research.generate_ai(
            ResearchInput(prompt="AI infrastructure", max_holdings=2, max_weight=0.5)
        )


@pytest.mark.parametrize(
    "constraints, message",
    [
        ({"required_tickers": ["NOW"]}, "requested companies"),
        ({"excluded_tickers": ["NVDA"]}, "excluded companies"),
    ],
)
def test_company_constraints_are_enforced(monkeypatch, constraints, message):
    reply = iter(responses())
    monkeypatch.setattr(ai_research, "call_response", lambda _: next(reply))
    with pytest.raises(ValueError, match=message):
        ai_research.generate_ai(
            ResearchInput(
                prompt="AI infrastructure",
                max_holdings=2,
                max_weight=0.5,
                **constraints,
            )
        )

import httpx
import pytest
from services.api.app.services import openrouter
from services.api.app.config import settings


def test_openrouter_transport_and_citations(monkeypatch):
    monkeypatch.setattr(settings, "llm_model", "meta-llama/llama-3.3-70b-instruct")

    def post(url, **kwargs):
        assert url == "https://openrouter.ai/api/v1/chat/completions"
        assert kwargs["json"]["model"] == settings.llm_model
        assert kwargs["json"]["plugins"] == [{"id": "web", "max_results": 5}]
        assert kwargs["json"]["max_tokens"] == 1200
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "Evidence",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url_citation": {
                                        "url": "https://example.com",
                                        "title": "Evidence",
                                    },
                                }
                            ],
                        },
                    }
                ]
            },
        )

    monkeypatch.setattr(openrouter.httpx, "post", post)
    result = openrouter.call_openrouter(
        {"instructions": "Research", "input": "AI", "tools": [{}]}
    )
    assert (
        result["output"][0]["content"][0]["annotations"][0]["url"]
        == "https://example.com"
    )


def test_openrouter_structured_extraction(monkeypatch):
    def post(url, **kwargs):
        body = kwargs["json"]
        assert "plugins" not in body
        assert body["provider"]["require_parameters"] is True
        assert body["response_format"]["json_schema"]["name"] == "proposal"
        assert body["max_tokens"] == 4096
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]},
        )

    monkeypatch.setattr(openrouter.httpx, "post", post)
    openrouter.call_openrouter(
        {
            "instructions": "Extract",
            "input": "Evidence",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "proposal",
                    "schema": {},
                    "strict": True,
                }
            },
        }
    )


def test_openrouter_themed_basket_extraction_uses_compact_budget(monkeypatch):
    def post(url, **kwargs):
        assert kwargs["json"]["max_tokens"] == 900
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]},
        )

    monkeypatch.setattr(openrouter.httpx, "post", post)
    openrouter.call_openrouter(
        {
            "instructions": "Extract",
            "input": "Evidence",
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "thematic_portfolio",
                    "schema": {},
                    "strict": True,
                }
            },
        }
    )


@pytest.mark.parametrize(
    "status,expected",
    [(402, "insufficient credits"), (401, "rejected"), (429, "unavailable")],
)
def test_openrouter_errors_are_sanitized(monkeypatch, status, expected):
    monkeypatch.setattr(
        openrouter.httpx,
        "post",
        lambda url, **kw: httpx.Response(
            status,
            request=httpx.Request("POST", url),
            text="sensitive provider details",
        ),
    )
    with pytest.raises(ValueError, match=expected) as error:
        openrouter.call_openrouter({"instructions": "Research", "input": "AI"})
    assert "sensitive" not in str(error.value)

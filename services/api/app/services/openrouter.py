"""OpenRouter chat transport normalized for the shared research validator."""

import httpx
from ..config import settings


def call_openrouter(payload):
    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": payload["instructions"]},
            {"role": "user", "content": payload["input"]},
        ],
        "max_tokens": 16000
        if payload.get("tools")
        or payload.get("text", {}).get("format", {}).get("name") == "thematic_portfolio"
        else 4096,
        "temperature": 0.2,
    }
    if payload.get("tools"):
        body["plugins"] = [{"id": "web", "max_results": 5}]
    if payload.get("text"):
        spec = payload["text"]["format"]
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {k: v for k, v in spec.items() if k != "type"},
        }
        body["provider"] = {"require_parameters": True}
    try:
        response = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=body,
            timeout=120,
        )
        if response.status_code == 402:
            raise ValueError(
                "OpenRouter has insufficient credits. Add credits to the configured account."
            )
        if response.status_code in (401, 403):
            raise ValueError(
                "OpenRouter rejected the API key or model access. Check the server credentials."
            )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise ValueError(
            "OpenRouter unavailable. Check model access and rate limits, then retry."
        ) from exc
    choices = data.get("choices") or []
    if not choices or choices[0].get("finish_reason") != "stop":
        raise ValueError(
            "OpenRouter research did not complete; no portfolio was created"
        )
    message = choices[0]["message"]
    if not isinstance(message.get("content"), str):
        raise ValueError("OpenRouter returned no research text")
    annotations = [
        {**a["url_citation"], "type": "url_citation"}
        for a in message.get("annotations", [])
        if a.get("type") == "url_citation" and isinstance(a.get("url_citation"), dict)
    ]
    return {
        "id": data.get("id"),
        "status": "completed",
        "usage": data.get("usage"),
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": message["content"],
                        "annotations": annotations,
                    }
                ],
            }
        ],
    }

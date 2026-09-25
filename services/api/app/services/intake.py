"""Clarify the user's brief before committing to stock research."""

import json
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal
from .ai_research import call_response, output_text


class Brief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required_tickers: list[str] = Field(default_factory=list)
    excluded_tickers: list[str] = Field(default_factory=list)
    ready: bool
    message: str
    theme: str
    sector: Literal[
        "",
        "Technology",
        "Industrials",
        "Utilities",
        "Healthcare",
        "Consumer discretionary",
        "Communication services",
        "Energy",
        "Financials",
        "Consumer staples",
        "Materials",
        "Real estate",
    ]
    holdings: int = Field(ge=2, le=50)
    max_weight: float = Field(ge=0.02, le=1)
    weighting: Literal["equal", "theme"]


def clarify(body):
    result = call_response(
        {
            "instructions": """You are Aquarius Baskets, a collaborative thematic portfolio research assistant. First understand the idea; do not jump to stock selection. Ask one or two concise, specific questions about an ambiguous theme, its subthemes/value chain, and whether to restrict a sector or span sectors. Explain examples when the user is unsure. Also establish holding count and equal vs theme-relevance weighting. Defaults are proposals, not user decisions. On the first turn always ask a useful narrowing question unless the user already supplies a clear focus, sector scope and weighting preference. On later turns, use both user and assistant history, accept 'you decide' or 'go ahead' as permission to use stated defaults. Do not repeat answered questions. Answer conceptual questions briefly without making unsupported current-performance claims, then ask what to explore. Set ready=true only when the user has given enough direction to build. Theme must summarize the entire agreed brief, preserving exclusions and other constraints. Sector may be empty for cross-sector themes. Weighting 'theme' means capped theme-relevance weights, not optimized returns or risk. Extract explicitly requested companies and listed ETF/ETP tickers into required_tickers, converting company names to US-listed symbols (for example ServiceNow is NOW). Listed funds such as DRAM, MAGS, VTI, TLT, GLD, and IBIT are eligible components when relevant. Extract exclusions into excluded_tickers. Do not infer required tickers from mere illustrative examples. Never invent financial data. Keep the user-facing message concise; do not narrate defaults, numeric field values or internal overrides.""",
            "input": json.dumps(
                {
                    "messages": [m.model_dump() for m in body.history]
                    or [{"role": "user", "text": m} for m in body.messages],
                    "current_portfolio": body.current_proposal.model_dump()
                    if body.current_proposal
                    else None,
                    "preferences": {
                        "sector": body.sector,
                        "holdings": body.max_holdings,
                        "max_weight": body.max_weight,
                        "weighting": body.weighting,
                    },
                }
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "research_brief",
                    "strict": True,
                    "schema": Brief.model_json_schema(),
                }
            },
        }
    )
    brief = Brief.model_validate_json(output_text(result))
    from .universe import explicit_company_constraints

    required, excluded = explicit_company_constraints(body.messages)
    brief.required_tickers = sorted((set(brief.required_tickers) | required) - excluded)
    brief.excluded_tickers = sorted((set(brief.excluded_tickers) | excluded) - required)
    return brief

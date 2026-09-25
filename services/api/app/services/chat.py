"""Conversation adapter: preview portfolios without saving or running a backtest."""

import re
from ..config import settings
from ..schemas import ResearchInput, ResearchChatInput, PortfolioInput
from .research import generate, THEMES
from .sectors import SECTORS
from .market import CATALOG
from .weights import allocate


def respond(body: ResearchChatInput):
    ai_enabled = settings.research_provider in ("openai", "openrouter")
    if ai_enabled:
        context = {
            "sector": body.sector,
            "max_holdings": body.max_holdings,
            "max_weight": body.max_weight,
            "weighting": body.weighting,
        }
        try:
            if body.current_proposal:
                latest = body.messages[-1]
                fixed = {}
                for i, h in enumerate(body.current_proposal.holdings):
                    match = re.search(
                        r"\b"
                        + re.escape(h.ticker)
                        + r"\b\s*(?:to|at|=|:)??\s*(\d+(?:\.\d+)?)\s*%",
                        latest,
                        re.I,
                    )
                    if match:
                        fixed[i] = float(match.group(1)) / 100
                rebalance = re.search(
                    r"\b(equal[ -]?weight|theme[ -]?(?:weight|relevance)|rebalance|reweight)\b",
                    latest,
                    re.I,
                )
                if fixed or rebalance:
                    proposal = body.current_proposal.model_copy(deep=True)
                    equal = bool(re.search(r"equal[ -]?weight", latest, re.I))
                    scores = [
                        1
                        if equal
                        else (
                            max(h.confidence or 0.5, 0.01) ** 2
                            if rebalance
                            else h.target_weight
                        )
                        for h in proposal.holdings
                    ]
                    weights = allocate(scores, body.max_weight, fixed)
                    for h, w in zip(proposal.holdings, weights):
                        h.target_weight = w
                    return {
                        **context,
                        "proposal": proposal.model_dump(),
                        "message": "I've adjusted the allocation and redistributed the remaining weight within your cap. The total is 100%; the companies and their research are unchanged.",
                        "warnings": [],
                    }
            from .intake import clarify

            brief = clarify(body)
            context = {
                "sector": brief.sector,
                "max_holdings": brief.holdings,
                "max_weight": brief.max_weight,
                "weighting": brief.weighting,
            }
            if not brief.ready:
                return {**context, "proposal": None, "message": brief.message}
            from .ai_research import generate_ai

            proposal, audit = generate_ai(
                ResearchInput(
                    prompt=brief.theme,
                    sector=brief.sector,
                    max_holdings=brief.holdings,
                    max_weight=brief.max_weight,
                    weighting=brief.weighting,
                    required_tickers=brief.required_tickers,
                    excluded_tickers=brief.excluded_tickers,
                )
            )
            method = "equal" if brief.weighting == "equal" else "capped theme-relevance"
            return {
                **context,
                "proposal": proposal.model_dump(),
                "message": f"{brief.message}\n\nHere are {len(proposal.holdings)} companies with {method} weights. Adjust any allocation below, or ask me to change it—for example, ‘set NVDA to 15%’.",
                "warnings": audit["warnings"],
            }
        except ValueError as exc:
            return {**context, "proposal": None, "message": str(exc)}
    sector = body.sector
    count = body.max_holdings
    cap = body.max_weight
    theme = None
    excluded = set()
    for index, message in enumerate(body.messages):
        lower = message.lower()
        matched = [
            name
            for name, (words, _) in THEMES.items()
            if any(re.search(r"\b" + re.escape(w) + r"\b", lower) for w in words)
        ]
        if matched and (
            theme is None
            or "sector" not in lower
            or "theme" in lower
            or "instead" in lower
        ):
            theme = message
        if index == len(body.messages) - 1:
            if re.search(r"\b(all sectors|any sector|across sectors)\b", lower):
                sector = ""
            for name in SECTORS:
                if re.search(
                    r"\b" + re.escape(name.lower()) + r"\s+sector\b", lower
                ) or re.search(
                    r"\bsector(?: to|:)?\s+" + re.escape(name.lower()) + r"\b", lower
                ):
                    sector = name
            if re.search(r"\btech(?:nology)? sector\b", lower):
                sector = "Technology"
            n = re.search(r"\b(\d+)\s*(?:stocks|companies|holdings|names)\b", lower)
            if n:
                count = int(n.group(1))
            percent = re.search(
                r"(?:max(?:imum)?|cap)\D{0,15}(\d+(?:\.\d+)?)\s*%", lower
            )
            if percent:
                cap = float(percent.group(1)) / 100
        if re.search(r"\b(exclude|remove|without|drop)\b", lower):
            names = {
                t
                for t in CATALOG
                if re.search(r"\b" + re.escape(t) + r"\b", message.upper())
            }
            if not names and settings.research_provider not in ("openai", "openrouter"):
                return {
                    "message": "Tell me the ticker to remove, for example “remove NVDA”. I can also change the sector, holding count, or maximum weight.",
                    "proposal": None,
                    "sector": sector,
                    "max_holdings": count,
                    "max_weight": cap,
                }
            excluded.update(names)
    if not 2 <= count <= 50 or not 0.02 <= cap <= 1:
        return {
            "sector": body.sector,
            "max_holdings": body.max_holdings,
            "max_weight": body.max_weight,
            "proposal": None,
            "message": "Choose 2–50 holdings and a maximum weight between 2% and 100%.",
        }
    context = {"sector": sector, "max_holdings": count, "max_weight": cap}
    if not theme and settings.research_provider not in ("openai", "openrouter"):
        return {
            **context,
            "message": "What theme would you like to explore? This demo can research AI infrastructure, semiconductors, clean energy, healthcare, or technology. A sector is optional.",
            "proposal": None,
        }
    if (
        settings.research_provider not in ("openai", "openrouter")
        and len(body.messages) > 1
    ):
        latest = body.messages[-1].lower()
        supported = any(
            re.search(r"\b" + re.escape(w) + r"\b", latest)
            for _, (words, _) in THEMES.items()
            for w in words
        ) or re.search(
            r"\b(sector|stocks|companies|holdings|names|cap|maximum|max|remove|exclude|without|drop)\b",
            latest,
        )
        if not supported:
            return {
                **context,
                "message": "In this demo, I can revise the theme, filter a sector, change the number of holdings or weight cap, and remove tickers. Try “make it 5 holdings” or “remove NVDA”. Open-ended discussion is available when AI research is configured.",
                "proposal": None,
            }
    try:
        prompt = (
            "\n".join(body.messages)
            if settings.research_provider in ("openai", "openrouter")
            else theme
        )
        # Explicit exclusions are applied deterministically after catalog selection.
        if settings.research_provider not in ("openai", "openrouter"):
            prompt = re.split(
                r"\b(?:exclude|remove|without|drop)\b", prompt, flags=re.I
            )[0].strip()
            prompt = re.sub(r"\bonly\b", "", prompt, flags=re.I)
        request = ResearchInput(
            prompt=prompt if len(prompt) >= 8 else f"Theme: {prompt}",
            sector=sector,
            max_holdings=count,
            max_weight=cap,
        )
        if settings.research_provider in ("openai", "openrouter"):
            from .ai_research import generate_ai

            proposal, audit = generate_ai(request)
        else:
            proposal, audit = generate(request)
        kept = [h for h in proposal.holdings if h.ticker not in excluded]
        if not kept or 1 / len(kept) > cap + 1e-9:
            raise ValueError(
                "Too few matching companies for that weight cap. Increase the maximum weight, remove the sector filter, or choose another theme."
            )
        for h in kept:
            h.target_weight = 1 / len(kept)
        proposal = PortfolioInput(
            name=proposal.name,
            symbol=proposal.symbol,
            description="\n".join(body.messages)
            + f"\nSector: {sector or 'All sectors'}",
            holdings=kept,
        )
        return {
            **context,
            "proposal": proposal.model_dump(),
            "message": f"I put together {len(kept)} companies for {proposal.name.lower()}{' in the ' + sector.lower() + ' sector' if sector else ' across sectors'}. Each has a company reference and an equal starting weight. You can refine this basket here, or open it in the editor to adjust allocations and run a backtest.",
            "warnings": audit["warnings"],
        }
    except ValueError as exc:
        return {**context, "message": str(exc), "proposal": None}

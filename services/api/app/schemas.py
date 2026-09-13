from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Source(StrictModel):
    url: str = Field(pattern=r"^https://", max_length=2000)
    title: str = Field(max_length=300)
    snippet: str = Field(default="", max_length=2000)
    retrieved_at: str | None = None


class Holding(StrictModel):
    ticker: str = Field(pattern=r"^[A-Z][A-Z0-9.\-]{0,9}$")
    company_name: str = Field(default="", max_length=200)
    target_weight: float = Field(ge=0, le=1)
    theme_tag: str = Field(default="", max_length=100)
    rationale: str = Field(default="", max_length=4000)
    confidence: float | None = Field(default=None, ge=0, le=1)
    sources: list[Source] = Field(default_factory=list, max_length=10)

    @field_validator("ticker", mode="before")
    @classmethod
    def canonical(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class PortfolioInput(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    symbol: str = Field(default="", max_length=12)
    description: str = Field(default="", max_length=4000)
    holdings: list[Holding] = Field(default_factory=list, max_length=50)

    @field_validator("name")
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError("Name must not be blank")
        return v.strip()

    @field_validator("holdings")
    @classmethod
    def valid_holdings(cls, v):
        if len({h.ticker for h in v}) != len(v):
            raise ValueError("Duplicate holdings are not allowed")
        if v and abs(sum(h.target_weight for h in v) - 1) > 1e-6:
            raise ValueError(
                "Weights must sum to 100%. Normalize explicitly before saving."
            )
        return v


class PortfolioUpdate(PortfolioInput):
    expected_version: int = Field(ge=1)


class HoldingsUpdate(StrictModel):
    expected_version: int = Field(ge=1)
    holdings: list[Holding] = Field(max_length=50)


class BacktestInput(StrictModel):
    etf_id: str
    portfolio_version: int = Field(ge=1)
    start_date: date
    end_date: date
    initial_capital: float = Field(default=10000, ge=100, le=1e9)
    benchmark: Literal["SPY", "QQQ"] = "SPY"
    rebalance_frequency: Literal["none", "monthly", "quarterly"] = "monthly"
    commission_bps: float = Field(default=0, ge=0, le=100)
    slippage_bps: float = Field(default=0, ge=0, le=100)
    dividend_mode: Literal["total_return"] = "total_return"
    risk_free_rate: float = Field(default=0, ge=0, le=0.25)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.start_date >= self.end_date:
            raise ValueError("Start date must precede end date")
        if self.end_date > date.today():
            raise ValueError("End date cannot be in the future")
        if (self.end_date - self.start_date).days > 3653:
            raise ValueError("Maximum history is 10 years")
        if self.start_date < date(2000, 1, 1):
            raise ValueError("History starts in 2000")
        return self


class ResearchInput(StrictModel):
    prompt: str = Field(min_length=8, max_length=2000)
    max_holdings: int = Field(default=8, ge=2, le=20)
    max_weight: float = Field(default=0.25, ge=0.05, le=1)


class PreviewInput(StrictModel):
    etf_id: str
    portfolio_version: int = Field(ge=1)
    investment: float = Field(ge=1, le=1e7)


class PaperInput(StrictModel):
    preview_id: str
    confirmed: Literal[True]

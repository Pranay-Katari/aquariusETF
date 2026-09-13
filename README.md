# Aquarius — custom thematic portfolio studio

A working implementation of the first usable product in `custom_etf_platform_build_spec.pdf`: a Next.js portfolio editor, FastAPI service, deterministic daily backtester, persisted portfolio versions, TradingView charts, research initialization and paper-basket previews.

**The default local workspace uses synthetic prices, SQLite and a curated research catalog. It does not show real investment performance.** Market data, Supabase, Redis and AI research are configurable adapters; no accounts or paid services are provisioned by this repository.

## Run locally

Requirements: Python 3.13 or 3.14, Node.js 22+, npm. From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
npm ci --prefix apps/web
./scripts/dev.sh
```

Open http://127.0.0.1:3000. The API is at http://127.0.0.1:8000 and its interactive contract is at http://127.0.0.1:8000/docs. You can also launch the API with `.venv/bin/python main.py` and the web app separately with `npm run dev --prefix apps/web`.

For a local production web build, run `npm run build --prefix apps/web` followed by `npm run start --prefix apps/web` while the API is running.

No environment file is needed for demo mode. Copy `.env.example` to `.env` and `apps/web/.env.example` to `apps/web/.env.local` when configuring integrations. Restart both services after changing configuration. Local state lives in `data/` and survives restarts. The browser does not store portfolios in localStorage.

Alternatively, `docker compose up --build` starts the local demo with Redis and a persistent data volume. Ports bind only to loopback. Docker configuration is provided but has not been exercised on this host.

## What works

- Dashboard and manual portfolio construction; add/remove/clear, inline weights, equal weighting and explicit normalization. Server validation rejects duplicates, unsupported tickers, negative/nonfinite weights and invalid totals. Empty portfolios may be stored through the API as drafts; a backtest requires holdings.
- Versioned save with optimistic concurrency checks. A backtest owns an immutable holdings snapshot, full configuration, engine version, price checksum and artifact checksum. Portfolio edits visibly mark prior results stale.
- Explicit Generate Backtest queues persisted work and shows progress. Failed/canceled jobs remain in history. Restart-interrupted jobs are marked failed with a retry instruction.
- NYSE session alignment, first-session close allocation, fractional total-return units, monthly/quarterly/no rebalancing, fees and slippage, SPY/QQQ comparison. Incomplete price histories fail rather than being silently filled.
- NAV/normalized chart, daily range selection, full-period metrics, net holding contributions, current/average weights in artifacts, drawdown episodes, rolling 21-session returns and a rebalance ledger. Compare saved backtests and export the entire reproducible artifact as JSON.
- Source-linked curated research without credentials. Optional OpenAI web-search research followed by structured extraction and deterministic validation. Every model-supplied URL must occur in actual tool search sources, symbols must pass provider validation, and code computes equal weights within the specified cap. Users still need to review whether evidence supports the rationale; citation presence alone cannot establish truth.
- Persisted buy-only paper order preview, cent rounding, residual cash and server-side Alpaca paper adapter. Submission requires a fresh broker-validated preview, explicit confirmation, authenticated designated account owner and server-side enablement. Client order IDs and durable intents prevent duplicate submissions on retries; uncertain submissions are reconciled explicitly. There is no live-trading code path.
- Configurable Redis cache-aside; Parquet history and result artifacts remain durable when Redis is flushed. Optional private Supabase Storage mirror can restore local objects after disk loss.

## Architecture

```text
apps/web/                 Next.js App Router, React, TypeScript, Lightweight Charts
services/api/app/         FastAPI, configuration, auth, SQLAlchemy models, contracts
services/api/app/services/ market, engine, analytics, research, storage, paper adapter
services/api/tests/        golden accounting, API ownership/versioning, cache, research tests
infra/sql/001_initial.sql  PostgreSQL schema and read-only owner RLS policies
infra/docker/             API and standalone web images
```

The same business layer uses SQLite locally and PostgreSQL in production. Relational ETF/holding/backtest/research/order tables store some versioned documents as JSON. Metrics and artifact paths are embedded in `backtests`, research sources in `research_runs` and holdings; these are intentionally fewer tables than the illustrative schema in the PDF. All writes go through FastAPI so browser REST writes cannot bypass validation, versioning or order approval rules.

## Connect real daily market data

Set `MARKET_DATA_PROVIDER=alphavantage` and `MARKET_DATA_API_KEY`. This adapter uses `TIME_SERIES_DAILY_ADJUSTED` with full history, which requires an appropriate provider entitlement. It caches normalized data, keeps full history in Parquet, and refreshes upstream data after 24 hours. The application never substitutes synthetic data when the live provider fails. Non-catalog symbols are validated on save; an unavailable or incomplete history fails the backtest clearly.

Provider prices are split- and dividend-adjusted. Simulated quantities are total-return units, **not actual brokerage share counts**. Brokerage sizing uses cash notional, not those simulated units. Market licensing, latency and vendor rate limits must be checked for your deployment.

## Supabase authentication, database and storage

1. Create a Supabase project and run `infra/sql/001_initial.sql` once in the SQL editor.
2. Set `APP_MODE=production`, `DATABASE_URL=postgresql+psycopg://...?...sslmode=require`, `SUPABASE_URL` and `SUPABASE_ANON_KEY` on the API. `DATABASE_URL` is a server-only privileged connection. Never place it in public variables.
3. Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` on the frontend. Register/sign in through the app and configure email confirmation in Supabase. API requests validate the bearer token through Supabase Auth; ownership is checked on every resource access.
4. To use object storage, create a **private** bucket and set `SUPABASE_STORAGE_BUCKET` and server-only `SUPABASE_SERVICE_ROLE_KEY`. Market objects are under `market/`; results under `artifacts/<user-id>/`. Otherwise provision a persistent mounted `DATA_DIR` and back it up.
5. Serve the app and API over HTTPS and set `CORS_ORIGINS` to the exact frontend origin. The frontend proxies API calls through `/api`; set `API_URL` at build time for the destination backend.

RLS is enabled on every application table. Authenticated users can read only their own records; child holding ownership follows its ETF. Public client writes are revoked. This is intentional: the application API performs transactions with ownership checks, and client direct writes would bypass those rules. The application user ID is stored as text to keep the SQLite/Postgres schema identical. User deletion currently requires server-side cleanup of application records and objects.

**Do not expose demo mode publicly.** It is a shared local identity with no authentication. Production mode refuses to boot without Supabase and PostgreSQL.

## Enable AI research

Set `RESEARCH_PROVIDER=openai`, `LLM_API_KEY`, and `LLM_MODEL` to a model available to your account that supports Responses, web search and structured outputs. No model or paid API is assumed automatically. The research flow performs two calls: primary-source discovery and schema-constrained extraction. It persists prompt, model, response IDs, tool calls, source metadata, token usage, validation and generated holdings. It never uses model-generated prices or performance.

The curated mode supports AI infrastructure, semiconductors, clean energy, healthcare and technology. It rejects unsupported free-text constraints rather than pretending to apply them. Holding count and concentration limits are enforced. Fundamental screens and fully deterministic semantic exclusions need a dedicated point-in-time fundamentals/classification provider; they are not supported in this release.

## Paper trading

Paper preview math works without an account. To enable submission, configure production authentication plus `PAPER_TRADING_ENABLED=true`, `PAPER_OWNER_USER_ID` and **paper-only** `ALPACA_API_KEY` / `ALPACA_API_SECRET`. The owner restriction prevents other app users from using the one server-configured brokerage account. Multi-user brokerage connections require a per-user secret store before extension.

The broker URL is fixed to `https://paper-api.alpaca.markets`; an environment variable cannot switch it to live. Preview checks buying power and tradable/fractionable status and expires after 10 minutes. Each basket is buy-only and does not net existing positions. Partial fills, rejections and unknown outcomes are possible; inspect `GET /v1/orders/{preview_id}` and call `POST /v1/orders/{preview_id}/reconcile`. Never infer that a timeout means no order was placed. Do not blindly create a new preview to retry an uncertain basket.

## Quantitative conventions

- Retrospective basket backtest, not a point-in-time selection strategy. Today's research can introduce selection and survivorship bias.
- First valid session close within the requested dates; all positive-weight constituents and benchmark must have every required NYSE session. No forward filling, delisting assumptions or IPO history fabrication.
- Rebalance at the close of the first session in a new month or quarter using precommitted target weights. Fractional adjusted-price units and cash are marked daily.
- Costs apply to absolute notional on buys and sells, including the initial allocation. Solve `post_cost_nav + rate * sum(abs(post_cost_nav * weights - old_exposure)) = pretrade_nav` so rebalancing is self-financing without negative cash.
- Total return and drawdown include initial costs. CAGR uses initial capital and elapsed calendar days. Daily-return risk statistics start between the first and second NAV observations, so initial execution cost is not treated as a full-day return.
- Volatility uses sample standard deviation and 252 sessions/year. Sharpe/alpha use arithmetic annualized daily returns and the configured annual risk-free rate. Sortino uses downside deviation relative to the daily risk-free rate. Undefined ratios are JSON null, rendered as an em dash.
- Turnover is half the absolute rebalance notional divided by mean NAV, excluding initial allocation. Holding contribution is cumulative mark-to-market P&L minus its trading costs divided by initial capital and reconciles to total return.
- The primary performance cards always describe the **full backtest**. Chart range controls change the displayed slice. Indexed mode rebases each displayed series to 100 at the start of that slice.

## Validation

```bash
.venv/bin/python -m pytest -q
npm run build --prefix apps/web
npm audit --prefix apps/web
```

Tests use isolated temporary databases and synthetic data; no external keys or financial actions. Golden fixtures cover exact two-stock NAV, monthly/quarterly schedules, costs/cash, contribution reconciliation, benchmark identity, known drawdown/CAGR, invalid/missing history, ownership and stale versions, Redis/durable-cache fallback, research source rejection and paper idempotency math. GitHub Actions runs tests and the production build.

## Scope and deployment limits

The initial product is implemented. The PDF's later roadmap phases remain later work: true intraday NAV, point-in-time universe/fundamental ingestion, walk-forward ML weighting, live trading, distributed workers, automated brokerage reconciliation and multi-user brokerage credential storage. Daily ranges are implemented; 1-minute data is rejected rather than mislabeled.

Background jobs and request limiting are single-process MVP implementations. Run **one API process/replica**. Before scaling, replace BackgroundTasks with a durable worker queue, make job claiming/restart recovery atomic across workers, and move the limiter to Redis or a gateway. Redis price miss serialization is local to the process; durable market objects assume one writer. No Sentry integration is configured; structured request and backtest logs are emitted. Real Supabase, market, AI, storage and paper integrations require credentials and have not been live-tested here.

## Official integration references

- [TradingView Lightweight Charts](https://tradingview.github.io/lightweight-charts/docs)
- [Supabase JWT authentication](https://supabase.com/docs/guides/auth/jwts)
- [Alpha Vantage daily adjusted data](https://www.alphavantage.co/documentation/)
- [OpenAI Responses web search](https://developers.openai.com/api/docs/guides/tools-web-search) and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Alpaca fractional trading](https://docs.alpaca.markets/us/docs/fractional-trading)

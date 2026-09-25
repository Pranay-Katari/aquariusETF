import hashlib
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import Literal
import pandas as pd
import numpy as np
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, delete, update
from sqlalchemy.orm import Session as DBSession
from .config import settings
from .db import (
    ETF,
    ETFHolding,
    Backtest,
    ResearchRun,
    ChatUsage,
    OrderPreview,
    Order,
    Session,
    init_db,
    get_db,
    uid,
    now,
)
from .schemas import (
    PortfolioInput,
    PortfolioUpdate,
    HoldingsUpdate,
    BacktestInput,
    OptimizeInput,
    WalkForwardInput,
    ResearchInput,
    ResearchChatInput,
    PreviewInput,
    PaperInput,
)
from .auth import current_user, limited_user
from .services.market import market, CATALOG, MarketError, sessions
from .services.engine import simulate, canonical_hash
from .services.research import generate
from .services.broker import broker, size_orders
from .services.storage import storage

log = logging.getLogger("aquarius")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app):
    init_db()
    # Single-process MVP jobs are persisted; a restart must not leave a perpetual spinner.
    with Session() as db:
        db.execute(
            update(Backtest)
            .where(Backtest.status.in_(["queued", "running"]))
            .values(
                status="failed",
                error="API restarted before completion. Generate a new backtest.",
            )
        )
        db.commit()
    yield


app = FastAPI(title="Aquarius Baskets API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    log.info(
        json.dumps(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }
        )
    )
    return response


@app.exception_handler(MarketError)
async def market_error(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": settings.app_mode,
        "market_provider": market.provider.name,
        "paper_enabled": settings.paper_trading_enabled,
        "research_mode": settings.research_provider,
    }


@app.get("/v1/me")
def me(user=Depends(current_user)):
    return {"id": user, "mode": settings.app_mode}


def owned(db, model, id, user):
    row = db.scalar(select(model).where(model.id == id, model.user_id == user))
    if not row:
        raise HTTPException(404, "Not found")
    return row


def locked_etf(db, id, user):
    # SQLite SELECT does not start a snapshot in legacy transaction mode.
    # Acquire the writer reservation before reading version plus holdings.
    if db.bind.dialect.name == "sqlite":
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    row = db.scalar(
        select(ETF).where(ETF.id == id, ETF.user_id == user).with_for_update()
    )
    if not row:
        raise HTTPException(404, "Not found")
    return row


def holdings_for(db, id):
    return [
        h.payload
        for h in db.scalars(
            select(ETFHolding)
            .where(ETFHolding.etf_id == id)
            .order_by(ETFHolding.ticker)
        )
    ]


def serialize_etf(db, etf):
    return {
        "id": etf.id,
        "name": etf.name,
        "symbol": etf.symbol,
        "description": etf.description,
        "config": etf.config or {},
        "version": etf.version,
        "holdings": holdings_for(db, etf.id),
        "created_at": etf.created_at.isoformat(),
        "updated_at": etf.updated_at.isoformat(),
    }


def validate_symbols(holdings):
    for h in holdings:
        if not market.validate_symbol(h.ticker):
            raise HTTPException(422, f"Unavailable ticker: {h.ticker}")


def create_portfolio(db, body, user):
    validate_symbols(body.holdings)
    etf = ETF(
        user_id=user,
        name=body.name,
        symbol=body.symbol,
        description=body.description,
        config=body.config,
    )
    db.add(etf)
    db.flush()
    for h in body.holdings:
        db.add(ETFHolding(etf_id=etf.id, ticker=h.ticker, payload=h.model_dump()))
    db.commit()
    return serialize_etf(db, etf)


@app.get("/v1/etfs")
def list_etfs(user=Depends(current_user), db: DBSession = Depends(get_db)):
    return [
        serialize_etf(db, e)
        for e in db.scalars(
            select(ETF).where(ETF.user_id == user).order_by(ETF.updated_at.desc())
        )
    ]


@app.post("/v1/etfs", status_code=201)
def create_etf(
    body: PortfolioInput, user=Depends(limited_user), db: DBSession = Depends(get_db)
):
    return create_portfolio(db, body, user)


@app.post("/v1/etfs/generate", status_code=201)
def generate_etf(
    body: ResearchInput, user=Depends(limited_user), db: DBSession = Depends(get_db)
):
    try:
        if settings.research_provider in ("openai", "openrouter"):
            from .services.ai_research import generate_ai

            proposal, audit = generate_ai(body)
        else:
            proposal, audit = generate(body)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    etf = create_portfolio(db, proposal, user)
    run = ResearchRun(user_id=user, etf_id=etf["id"], payload=audit)
    db.add(run)
    db.commit()
    return {"etf": etf, "research": audit, "research_run_id": run.id}


@app.get("/v1/etfs/{id}")
def get_etf(id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return serialize_etf(db, owned(db, ETF, id, user))


@app.patch("/v1/etfs/{id}")
def patch_etf(
    id: str,
    body: PortfolioUpdate,
    user=Depends(limited_user),
    db: DBSession = Depends(get_db),
):
    etf = owned(db, ETF, id, user)
    validate_symbols(body.holdings)
    changed = sorted(holdings_for(db, id), key=lambda h: h["ticker"]) != sorted(
        [h.model_dump() for h in body.holdings], key=lambda h: h["ticker"]
    )
    new_version = body.expected_version + int(changed)
    result = db.execute(
        update(ETF)
        .where(ETF.id == id, ETF.user_id == user, ETF.version == body.expected_version)
        .values(
            name=body.name,
            symbol=body.symbol,
            description=body.description,
            config=body.config,
            version=new_version,
            updated_at=now(),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            409, "Portfolio changed in another session. Reload before saving."
        )
    db.execute(delete(ETFHolding).where(ETFHolding.etf_id == id))
    for h in body.holdings:
        db.add(ETFHolding(etf_id=id, ticker=h.ticker, payload=h.model_dump()))
    db.commit()
    db.refresh(etf)
    return serialize_etf(db, etf)


@app.delete("/v1/etfs/{id}", status_code=204)
def delete_etf(
    id: str, user=Depends(limited_user), db: DBSession = Depends(get_db)
):
    """Permanently remove one of the signed-in user's containers and its history."""
    etf = owned(db, ETF, id, user)
    preview_ids = list(
        db.scalars(select(OrderPreview.id).where(OrderPreview.etf_id == id))
    )
    if preview_ids:
        db.execute(delete(Order).where(Order.preview_id.in_(preview_ids)))
    db.execute(delete(OrderPreview).where(OrderPreview.etf_id == id))
    db.execute(delete(ResearchRun).where(ResearchRun.etf_id == id))
    db.execute(delete(Backtest).where(Backtest.etf_id == id))
    db.delete(etf)
    db.commit()


@app.put("/v1/etfs/{id}/holdings")
def put_holdings(
    id: str,
    body: HoldingsUpdate,
    user=Depends(limited_user),
    db: DBSession = Depends(get_db),
):
    etf = owned(db, ETF, id, user)
    try:
        payload = PortfolioUpdate(
            name=etf.name,
            symbol=etf.symbol,
            description=etf.description,
            holdings=body.holdings,
            expected_version=body.expected_version,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return patch_etf(id, payload, user, db)


def summary(row):
    return {
        "id": row.id,
        "etf_id": row.etf_id,
        "portfolio_version": row.portfolio_version,
        "status": row.status,
        "config": row.config,
        "metrics": row.metrics,
        "warnings": row.warnings,
        "error": row.error,
        "engine_version": row.engine_version,
        "checksum": row.checksum,
        "created_at": row.created_at.isoformat(),
    }


def run_backtest(id):
    started = time.perf_counter()
    with Session() as db:
        row = db.get(Backtest, id)
        if not row or row.status == "canceled":
            return
        row.status = "running"
        db.commit()
        try:
            cfg = row.config
            start = date.fromisoformat(cfg["start_date"])
            end = date.fromisoformat(cfg["end_date"])
            symbols = sorted(
                {h["ticker"] for h in row.snapshot if h["target_weight"] > 0}
                | {cfg["benchmark"]}
            )
            history = {s: market.prices(s, start, end) for s in symbols}
            expected = set(sessions(start, end))
            for symbol, series in history.items():
                missing = expected - set(series.index)
                if missing:
                    raise MarketError(
                        f"{symbol}: {len(missing)} missing trading sessions (first {min(missing)}). Select a date range with complete common history."
                    )
            prices = pd.DataFrame(
                {
                    s: series
                    for s, series in history.items()
                    if s != cfg["benchmark"]
                    or any(h["ticker"] == s for h in row.snapshot)
                }
            )
            result = simulate(prices, history[cfg["benchmark"]], row.snapshot, cfg)
            result["metadata"].update(
                {
                    "portfolio_version": row.portfolio_version,
                    "provenance": market.provenance(),
                    "data_checksum": canonical_hash(
                        {
                            s: [[str(d), float(v)] for d, v in bars.items()]
                            for s, bars in history.items()
                        }
                    ),
                }
            )
            warnings = [
                "Retrospective basket: today’s constituent selection introduces survivorship and selection bias. This is not a point-in-time strategy test."
            ]
            if market.provenance()["synthetic"]:
                warnings.insert(
                    0,
                    "SYNTHETIC DEMO DATA — simulated price paths, not historical market performance.",
                )
            result["warnings"] = warnings
            root = settings.data_dir / "artifacts"
            root.mkdir(parents=True, exist_ok=True)
            artifact = root / f"{id}.json"
            data = json.dumps(result, sort_keys=True, allow_nan=False).encode()
            temp = artifact.with_suffix(".tmp")
            temp.write_bytes(data)
            temp.replace(artifact)
            storage.upload(
                f"artifacts/{row.user_id}/{id}.json", artifact, "application/json"
            )
            db.refresh(row)
            if row.status == "canceled":
                return
            completed = db.execute(
                update(Backtest)
                .where(Backtest.id == id, Backtest.status == "running")
                .values(
                    artifact_path=str(artifact),
                    checksum=hashlib.sha256(data).hexdigest(),
                    metrics=result["metrics"],
                    warnings=warnings,
                    status="completed",
                )
            )
            db.commit()
            if completed.rowcount != 1:
                return
            log.info(
                json.dumps(
                    {
                        "backtest_id": id,
                        "duration_seconds": time.perf_counter() - started,
                        "status": "completed",
                    }
                )
            )
        except Exception as exc:
            db.rollback()
            row = db.get(Backtest, id)
            db.refresh(row)
            if row.status != "canceled":
                row.status = "failed"
                row.error = (
                    str(exc)[:1000]
                    if isinstance(exc, ValueError)
                    else "Backtest failed. Check server logs and retry."
                )
                db.commit()
            log.exception("backtest_failed %s", id)


@app.post("/v1/backtests", status_code=202)
def create_backtest(
    body: BacktestInput,
    tasks: BackgroundTasks,
    user=Depends(limited_user),
    db: DBSession = Depends(get_db),
):
    etf = locked_etf(db, body.etf_id, user)
    if etf.version != body.portfolio_version:
        raise HTTPException(
            409, "Save or reload the current portfolio version before running"
        )
    snapshot = holdings_for(db, etf.id)
    if not snapshot:
        raise HTTPException(422, "Add holdings before generating a backtest")
    row = Backtest(
        user_id=user,
        etf_id=etf.id,
        portfolio_version=etf.version,
        config=body.model_dump(mode="json"),
        snapshot=snapshot,
    )
    db.add(row)
    db.commit()
    tasks.add_task(run_backtest, row.id)
    return summary(row)


@app.post("/v1/etfs/{id}/optimize")
def optimize_weights(
    id: str,
    body: OptimizeInput,
    user=Depends(limited_user),
    db: DBSession = Depends(get_db),
):
    """Search constrained whole-percent allocations over the current backtest period.

    This is deliberately a retrospective exploration tool: it never claims to predict
    future returns and does not save the proposed weights automatically.
    """
    etf = owned(db, ETF, id, user)
    if etf.version != body.portfolio_version:
        raise HTTPException(409, "Save or reload the current portfolio before optimizing")
    holdings = holdings_for(db, id)
    count = len(holdings)
    if not 2 <= count <= 25:
        raise HTTPException(422, "Optimization requires 2–25 holdings")
    cfg = body.model_dump(mode="json")
    start, end = body.start_date, body.end_date
    try:
        symbols = sorted({h["ticker"] for h in holdings} | {body.benchmark})
        history = {symbol: market.prices(symbol, start, end) for symbol in symbols}
        expected = set(sessions(start, end))
        if any(expected - set(series.index) for series in history.values()):
            raise MarketError("The selected period has incomplete price history")
        prices = pd.DataFrame({h["ticker"]: history[h["ticker"]] for h in holdings})
        benchmark = history[body.benchmark]
        rng = np.random.default_rng(int(canonical_hash({"id": id, "config": cfg})[:16], 16))
        # Each name gets at least 1% and at most 50%, preventing a trivial one-name answer.
        candidates = [np.full(count, 100 // count, dtype=int)]
        candidates[0][: 100 % count] += 1
        if count == 2:
            # With the 50% cap, this is the only valid two-name allocation.
            candidates = [np.array([50, 50], dtype=int)]
        else:
            while len(candidates) < 500:
                weights = np.ones(count, dtype=int)
                remaining = 100 - count
                proposal = weights + rng.multinomial(remaining, rng.dirichlet(np.ones(count)))
                if proposal.max() <= 50:
                    candidates.append(proposal)
        best_weights, best_result = candidates[0], None
        for candidate in candidates:
            trial = [{**holding, "target_weight": int(weight) / 100} for holding, weight in zip(holdings, candidate)]
            outcome = simulate(prices, benchmark, trial, cfg)
            if best_result is None or outcome["metrics"]["ending_value"] > best_result["metrics"]["ending_value"]:
                best_weights, best_result = candidate, outcome
    except MarketError as exc:
        raise HTTPException(422, str(exc))
    return {
        "holdings": [{**holding, "target_weight": int(weight) / 100} for holding, weight in zip(holdings, best_weights)],
        "metrics": best_result["metrics"],
        "constraints": {"min_weight_percent": 1, "max_weight_percent": 50, "candidates_tested": len(candidates)},
        "warning": "In-sample optimization: these weights maximize historical ending value only over the selected period and are prone to overfitting. Review before saving or backtesting.",
    }


@app.post("/v1/etfs/{id}/walk-forward")
def walk_forward_validate(
    id: str,
    body: WalkForwardInput,
    user=Depends(limited_user),
    db: DBSession = Depends(get_db),
):
    """Optimize only on each training window, then score the next unseen sessions."""
    etf = owned(db, ETF, id, user)
    if etf.version != body.portfolio_version:
        raise HTTPException(409, "Save or reload the current portfolio before validating")
    holdings = holdings_for(db, id)
    count = len(holdings)
    if not 2 <= count <= 25:
        raise HTTPException(422, "Walk-forward validation requires 2–25 holdings")
    cfg = body.model_dump(mode="json", exclude={"test_sessions"})
    try:
        symbols = sorted({h["ticker"] for h in holdings} | {body.benchmark})
        history = {symbol: market.prices(symbol, body.start_date, body.end_date) for symbol in symbols}
        frame = pd.DataFrame(history).dropna().sort_index()
        if len(frame) < body.test_sessions * 3 + 126:
            raise MarketError(
                "Choose a longer period: walk-forward validation needs 126 training sessions plus three unseen test windows"
            )
        # Three expanding training windows, each followed by a strictly unseen test block.
        first_test = len(frame) - body.test_sessions * 3
        folds = []
        for fold in range(3):
            train_end = first_test + fold * body.test_sessions
            train_prices = frame.iloc[:train_end]
            test_prices = frame.iloc[train_end : train_end + body.test_sessions]
            seed = int(canonical_hash({"id": id, "fold": fold, "config": cfg})[:16], 16)
            rng = np.random.default_rng(seed)
            candidates = [np.full(count, 100 // count, dtype=int)]
            candidates[0][: 100 % count] += 1
            if count == 2:
                candidates = [np.array([50, 50], dtype=int)]
            else:
                while len(candidates) < 300:
                    proposal = np.ones(count, dtype=int) + rng.multinomial(
                        100 - count, rng.dirichlet(np.ones(count))
                    )
                    if proposal.max() <= 50:
                        candidates.append(proposal)
            best_weights, best_training = candidates[0], None
            for candidate in candidates:
                trial = [
                    {**holding, "target_weight": int(weight) / 100}
                    for holding, weight in zip(holdings, candidate)
                ]
                outcome = simulate(
                    train_prices[[h["ticker"] for h in holdings]],
                    train_prices[body.benchmark],
                    trial,
                    cfg,
                )
                if best_training is None or outcome["metrics"]["ending_value"] > best_training["metrics"]["ending_value"]:
                    best_weights, best_training = candidate, outcome
            selected = [
                {**holding, "target_weight": int(weight) / 100}
                for holding, weight in zip(holdings, best_weights)
            ]
            unseen = simulate(
                test_prices[[h["ticker"] for h in holdings]],
                test_prices[body.benchmark],
                selected,
                cfg,
            )
            folds.append(
                {
                    "training_end": str(train_prices.index[-1]),
                    "test_start": str(test_prices.index[0]),
                    "test_end": str(test_prices.index[-1]),
                    "weights": {h["ticker"]: int(w) for h, w in zip(holdings, best_weights)},
                    "training_total_return": best_training["metrics"]["total_return"],
                    "unseen_total_return": unseen["metrics"]["total_return"],
                    "unseen_benchmark_return": unseen["metrics"]["benchmark_return"],
                    "unseen_max_drawdown": unseen["metrics"]["max_drawdown"],
                }
            )
    except (MarketError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    unseen_returns = [fold["unseen_total_return"] for fold in folds]
    benchmark_returns = [fold["unseen_benchmark_return"] for fold in folds]
    return {
        "folds": folds,
        "summary": {
            "median_unseen_return": float(np.median(unseen_returns)),
            "mean_unseen_return": float(np.mean(unseen_returns)),
            "mean_unseen_benchmark_return": float(np.mean(benchmark_returns)),
            "win_rate_vs_benchmark": float(np.mean(np.array(unseen_returns) > np.array(benchmark_returns))),
        },
        "warning": "Each fold chooses weights only from data available before its test window. This reduces, but does not eliminate, selection bias; it is not a forecast or a recommendation.",
    }


@app.get("/v1/etfs/{id}/backtests")
def list_backtests(
    id: str, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    owned(db, ETF, id, user)
    return [
        summary(b)
        for b in db.scalars(
            select(Backtest)
            .where(Backtest.etf_id == id, Backtest.user_id == user)
            .order_by(Backtest.created_at.desc())
        )
    ]


@app.get("/v1/etfs/{id}/research")
def research_history(
    id: str, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    owned(db, ETF, id, user)
    return [
        r.payload
        for r in db.scalars(
            select(ResearchRun).where(
                ResearchRun.etf_id == id, ResearchRun.user_id == user
            )
        )
    ]


@app.get("/v1/backtests/{id}")
def get_backtest(id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return summary(owned(db, Backtest, id, user))


@app.post("/v1/backtests/{id}/cancel")
def cancel(id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    row = owned(db, Backtest, id, user)
    if row.status not in ("queued", "running"):
        raise HTTPException(409, "Only queued or running jobs can be canceled")
    row.status = "canceled"
    db.commit()
    return summary(row)


def artifact(db, id, user):
    from pathlib import Path

    row = owned(db, Backtest, id, user)
    if row.status != "completed":
        raise HTTPException(409, "Backtest has not completed")
    path = Path(row.artifact_path)
    if not path.exists():
        try:
            storage.restore(f"artifacts/{user}/{id}.json", path)
        except Exception:
            raise HTTPException(503, "Artifact storage is unavailable")
    if not path.exists():
        raise HTTPException(503, "Artifact storage is unavailable")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != row.checksum:
        raise HTTPException(500, "Artifact checksum mismatch")
    return json.loads(data)


@app.get("/v1/backtests/{id}/artifact")
def get_artifact(id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return artifact(db, id, user)


@app.get("/v1/backtests/{id}/series")
def get_series(
    id: str,
    range: Literal["1D", "5D", "1M", "6M", "YTD", "1Y", "5Y", "MAX"] = "MAX",
    resolution: Literal["1d"] = "1d",
    user=Depends(current_user),
    db: DBSession = Depends(get_db),
):
    data = artifact(db, id, user)
    rows = data["series"]
    end = date.fromisoformat(rows[-1]["time"])
    if range == "1D":
        rows = rows[-1:]
    elif range == "5D":
        rows = rows[-5:]
    elif range != "MAX":
        start = (
            date(end.year, 1, 1)
            if range == "YTD"
            else end
            - timedelta(days={"1M": 31, "6M": 183, "1Y": 366, "5Y": 1827}[range])
        )
        rows = [r for r in rows if date.fromisoformat(r["time"]) >= start]
    return {
        "currency": "USD",
        "mode": "nav",
        "resolution": "1d",
        "portfolio": [{"time": r["time"], "value": r["portfolio_nav"]} for r in rows],
        "benchmark": [{"time": r["time"], "value": r["benchmark_nav"]} for r in rows],
        "drawdown": [{"time": r["time"], "value": r["drawdown"] * 100} for r in rows],
    }


@app.get("/v1/backtests/{id}/attribution")
def attribution(id: str, user=Depends(current_user), db: DBSession = Depends(get_db)):
    return artifact(db, id, user)["attribution"]


@app.get("/v1/market/symbols")
def symbols(q: str = "", user=Depends(current_user)):
    from .services.universe import LISTED_EQUITIES

    universe = {
        **{s: (n, "US-listed equity") for s, n in LISTED_EQUITIES.items()},
        **CATALOG,
    }
    matches = [
        {"ticker": s, "company_name": v[0], "theme_tag": v[1]}
        for s, v in universe.items()
        if q.lower() in (s + " " + v[0]).lower()
    ]
    return sorted(
        matches, key=lambda item: (item["ticker"] != q.upper(), item["ticker"])
    )[:100]


@app.get("/v1/market/bars/{ticker}")
def bars(ticker: str, start: date, end: date, user=Depends(limited_user)):
    from .schemas import Holding

    try:
        ticker = Holding(ticker=ticker, target_weight=1).ticker
    except ValueError:
        raise HTTPException(422, "Invalid ticker")
    if start >= end or end > date.today() or (end - start).days > 3653:
        raise HTTPException(422, "Invalid date range")
    data = market.prices(ticker, start, end)
    return {
        "symbol": ticker,
        "timeframe": "1d",
        "provenance": market.provenance(),
        "bars": [
            {"timestamp": str(d) + "T00:00:00Z", "adjusted_close": float(v)}
            for d, v in data.items()
        ],
    }


@app.post("/v1/orders/preview", status_code=201)
def preview(
    body: PreviewInput, user=Depends(limited_user), db: DBSession = Depends(get_db)
):
    etf = locked_etf(db, body.etf_id, user)
    if etf.version != body.portfolio_version:
        raise HTTPException(409, "Portfolio version changed")
    holdings = holdings_for(db, etf.id)
    if not holdings:
        raise HTTPException(422, "Portfolio is empty")
    id = uid()
    orders, residual = size_orders(holdings, body.investment, id)
    if not orders:
        raise HTTPException(422, "Investment is too small")
    checked = False
    if settings.paper_trading_enabled:
        if settings.app_mode == "demo" or user != settings.paper_owner_user_id:
            raise HTTPException(
                403, "Paper trading requires the configured authenticated account owner"
            )
        try:
            account = broker.account()
            if (
                account.get("trading_blocked")
                or float(account["buying_power"]) < body.investment
            ):
                raise ValueError("Insufficient buying power or account blocked")
            for order in orders:
                asset = broker.asset(order["symbol"])
                if not asset.get("tradable") or not asset.get("fractionable"):
                    raise ValueError(
                        f"{order['symbol']} is not tradable with fractional orders"
                    )
            checked = True
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    payload = {
        "id": id,
        "environment": "paper",
        "investment": body.investment,
        "orders": orders,
        "residual_cash": residual,
        "broker_validated": checked,
        "expires_at": (now() + timedelta(minutes=10)).isoformat(),
        "warning": "Buy-only basket; existing account positions are not rebalanced. Market order fills are not guaranteed.",
    }
    db.add(
        OrderPreview(
            id=id,
            user_id=user,
            etf_id=etf.id,
            portfolio_version=etf.version,
            payload=payload,
        )
    )
    db.commit()
    return payload


@app.post("/v1/orders/paper")
def submit_paper(
    body: PaperInput, user=Depends(limited_user), db: DBSession = Depends(get_db)
):
    if (
        settings.app_mode == "demo"
        or not settings.paper_trading_enabled
        or user != settings.paper_owner_user_id
    ):
        raise HTTPException(
            403,
            "Paper submission is disabled or this user is not the configured broker account owner",
        )
    row = owned(db, OrderPreview, body.preview_id, user)
    etf = owned(db, ETF, row.etf_id, user)
    if row.portfolio_version != etf.version:
        raise HTTPException(409, "Portfolio changed. Generate a new preview.")
    if datetime.fromisoformat(row.payload["expires_at"]) < now():
        raise HTTPException(409, "Preview expired. Generate a new preview.")
    if not row.payload["broker_validated"]:
        raise HTTPException(409, "Preview has not been validated by the broker")
    results = []
    for intent in row.payload["orders"]:
        existing = db.scalar(
            select(Order).where(Order.client_order_id == intent["client_order_id"])
        )
        if existing:
            results.append(existing.payload)
            continue
        record = Order(
            user_id=user,
            preview_id=row.id,
            client_order_id=intent["client_order_id"],
            payload={"intent": intent, "status": "submitting"},
        )
        db.add(record)
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(
                409,
                "Submission already in progress. Check order status before retrying.",
            )
        try:
            result = broker.submit(intent)
            record.payload = {
                "intent": intent,
                "status": result["status"],
                "external_order_id": result["id"],
            }
        except Exception:
            # An ambiguous timeout must never trigger an untracked second submission.
            record.payload = {
                "intent": intent,
                "status": "unknown",
                "message": "Submission outcome uncertain. Reconcile this client order ID before retrying.",
            }
        db.commit()
        results.append(record.payload)
        if record.payload["status"] == "unknown":
            break
    return {"environment": "paper", "orders": results}


@app.get("/v1/orders/{preview_id}")
def order_status(
    preview_id: str, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    owned(db, OrderPreview, preview_id, user)
    return [
        o.payload
        for o in db.scalars(
            select(Order).where(Order.preview_id == preview_id, Order.user_id == user)
        )
    ]


@app.get("/v1/etfs/{id}/paper-orders")
def bucket_paper_orders(
    id: str, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    """Return only broker activity that originated from this saved ETF bucket."""
    owned(db, ETF, id, user)
    previews = list(
        db.scalars(
            select(OrderPreview)
            .where(OrderPreview.etf_id == id, OrderPreview.user_id == user)
            .order_by(OrderPreview.created_at.desc())
        )
    )
    preview_ids = [preview.id for preview in previews]
    orders_by_preview: dict[str, list[dict]] = {preview_id: [] for preview_id in preview_ids}
    if preview_ids:
        for order in db.scalars(
            select(Order).where(Order.preview_id.in_(preview_ids), Order.user_id == user)
        ):
            orders_by_preview[order.preview_id].append(order.payload)
    return [
        {
            "id": preview.id,
            "investment": preview.payload.get("investment"),
            "created_at": preview.created_at.isoformat(),
            "expires_at": preview.payload.get("expires_at"),
            "orders": orders_by_preview[preview.id],
        }
        for preview in previews
    ]


@app.post("/v1/orders/{preview_id}/reconcile")
def reconcile(
    preview_id: str, user=Depends(limited_user), db: DBSession = Depends(get_db)
):
    owned(db, OrderPreview, preview_id, user)
    for order in db.scalars(
        select(Order).where(Order.preview_id == preview_id, Order.user_id == user)
    ):
        try:
            result = broker.lookup(order.client_order_id)
            order.payload = {
                **order.payload,
                "status": result["status"],
                "external_order_id": result["id"],
                "filled_qty": result.get("filled_qty"),
                "filled_avg_price": result.get("filled_avg_price"),
                "filled_at": result.get("filled_at"),
            }
            db.commit()
        except ValueError:
            pass
    return order_status(preview_id, user, db)


@app.get("/v1/backtests/{id}/diagnostics")
def get_diagnostics(
    id: str, user=Depends(current_user), db: DBSession = Depends(get_db)
):
    from .services.analytics import diagnostics

    return diagnostics(artifact(db, id, user))


# Research chat is a preview-only action; portfolio creation remains explicit.


@app.post("/v1/research/chat")
def research_chat(
    body: ResearchChatInput, user=Depends(limited_user), db: DBSession = Depends(get_db)
):
    from .services.chat import respond
    from .services.cache import get_json, key, set_json

    usage = db.scalar(
        select(ChatUsage).where(ChatUsage.user_id == user).with_for_update()
    )
    current = now()
    window = timedelta(seconds=settings.chat_request_window_seconds)
    if usage is None:
        usage = ChatUsage(user_id=user, window_started_at=current, request_count=0)
        db.add(usage)
    elif current - usage.window_started_at >= window:
        usage.window_started_at = current
        usage.request_count = 0
    if usage.request_count >= settings.chat_request_limit:
        reset_at = usage.window_started_at + window
        raise HTTPException(
            429,
            f"Chat limit reached ({settings.chat_request_limit} requests). Try again after {reset_at.isoformat()}.",
        )
    usage.request_count += 1
    db.commit()

    # Cache only the research payload, not user/session data. A short TTL makes
    # repeated edits and accidental resends responsive without treating research
    # as permanent or current market information.
    cache_key = key("research-chat:v1", body.model_dump(mode="json"))
    cached = get_json(cache_key)
    if cached is not None:
        return {**cached, "cache_hit": True}
    response = respond(body)
    set_json(cache_key, response, ttl_seconds=900)
    return {**response, "cache_hit": False}

"""Server-side run metering. The UI meter is informational; this is the authority."""

from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ..config import settings
from ..db import Subscription, Usage, UsageEvent, now


def _usage(db, user_id: str) -> Usage:
    current = now()
    row = db.scalar(select(Usage).where(Usage.user_id == user_id).with_for_update())
    if row is None:
        row = Usage(user_id=user_id, period_start=current, period_end=current + timedelta(days=30), runs_limit=settings.free_run_limit)
        db.add(row)
        db.flush()
    elif current.replace(tzinfo=None) >= row.period_end.replace(tzinfo=None):
        row.period_start = current
        row.period_end = current + timedelta(days=30)
        row.runs_used = 0
        row.runs_limit = settings.free_run_limit
    return row


def is_pro(db, user_id: str) -> bool:
    subscription = db.get(Subscription, user_id)
    return bool(subscription and subscription.status in {"active", "trialing"})


def start_run(db, user_id: str, kind: str, run_key: str) -> UsageEvent:
    existing = db.get(UsageEvent, run_key)
    if existing:
        return existing
    usage = _usage(db, user_id)
    if not is_pro(db, user_id) and usage.runs_used >= usage.runs_limit:
        raise HTTPException(402, "limit_reached")
    usage.runs_used += 1
    event = UsageEvent(run_key=run_key, user_id=user_id, kind=kind)
    db.add(event)
    return event


def finish_run(db, run_key: str, ok: bool) -> None:
    event = db.get(UsageEvent, run_key)
    if not event or event.status != "pending":
        return
    event.status = "completed" if ok else "failed"
    if not ok and not is_pro(db, event.user_id):
        usage = _usage(db, event.user_id)
        usage.runs_used = max(0, usage.runs_used - 1)


def status(db, user_id: str) -> dict:
    usage = _usage(db, user_id)
    pro = is_pro(db, user_id)
    return {"plan": "pro" if pro else "free", "runs_used": usage.runs_used, "runs_limit": usage.runs_limit, "runs_remaining": None if pro else max(0, usage.runs_limit - usage.runs_used), "period_end": usage.period_end}

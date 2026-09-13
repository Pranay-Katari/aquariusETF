import time
import threading
from collections import defaultdict, deque
import httpx
from fastapi import Header, HTTPException, Depends
from .config import settings

DEMO_USER = "00000000-0000-0000-0000-000000000001"


def current_user(authorization: str | None = Header(default=None)) -> str:
    if settings.app_mode == "demo":
        return DEMO_USER
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to continue")
    try:
        response = httpx.get(
            f"{settings.supabase_url}/auth/v1/user",
            headers={
                "Authorization": authorization,
                "apikey": settings.supabase_anon_key,
            },
            timeout=10,
        )
        if response.status_code != 200:
            raise HTTPException(401, "Invalid or expired session")
        return response.json()["id"]
    except (httpx.HTTPError, KeyError):
        raise HTTPException(503, "Authentication service unavailable")


_hits = defaultdict(deque)
_lock = threading.Lock()


def limited_user(user: str = Depends(current_user)):
    # Local process limiter. Use gateway/distributed limits when running multiple replicas.
    with _lock:
        q = _hits[user]
        t = time.monotonic()
        while q and q[0] < t - 60:
            q.popleft()
        if len(q) >= 30:
            raise HTTPException(429, "Too many requests. Try again in a minute.")
        q.append(t)
    return user

"""Best-effort Redis cache for expensive, non-sensitive research responses."""

import hashlib
import json
import logging
from functools import lru_cache

import redis

from ..config import settings


@lru_cache(maxsize=1)
def _client():
    if not settings.redis_url:
        return None
    return redis.Redis.from_url(
        settings.redis_url, socket_connect_timeout=1, socket_timeout=1
    )


def key(namespace: str, value: object) -> str:
    digest = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return f"aquarius:{namespace}:{digest}"


def get_json(cache_key: str):
    client = _client()
    if not client:
        return None
    try:
        raw = client.get(cache_key)
        return json.loads(raw) if raw else None
    except (redis.RedisError, json.JSONDecodeError):
        logging.getLogger(__name__).warning("redis_cache_unavailable")
        return None


def set_json(cache_key: str, value: object, ttl_seconds: int):
    client = _client()
    if not client:
        return
    try:
        client.setex(cache_key, ttl_seconds, json.dumps(value, default=str))
    except redis.RedisError:
        logging.getLogger(__name__).warning("redis_cache_unavailable")

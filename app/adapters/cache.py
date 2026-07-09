import json
from contextlib import suppress
from typing import Any, cast

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


def _client() -> Redis | None:
    url = get_settings().redis_url
    return Redis.from_url(url, decode_responses=True, socket_timeout=0.2) if url else None


def get_json(key: str) -> Any | None:
    client = _client()
    if client is None:
        return None
    try:
        value = cast(str | bytes | None, client.get(key))
        return json.loads(value) if value else None
    except (RedisError, json.JSONDecodeError):
        return None


def set_json(key: str, value: Any, ttl_seconds: int = 60) -> None:
    client = _client()
    if client:
        with suppress(RedisError):
            client.setex(key, ttl_seconds, json.dumps(value, default=str))


def delete_pattern(pattern: str) -> None:
    client = _client()
    if client:
        with suppress(RedisError):
            keys = list(client.scan_iter(match=pattern, count=100))
            if keys:
                client.delete(*keys)

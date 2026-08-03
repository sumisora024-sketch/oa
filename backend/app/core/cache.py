import json
import time
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


class SessionCache:
    def __init__(self) -> None:
        self._fallback: dict[str, tuple[float, str]] = {}
        self._redis: Redis | None = None
        settings = get_settings()
        try:
            client = Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=1)
            client.ping()
            self._redis = client
        except RedisError:
            self._redis = None

    @property
    def using_redis(self) -> bool:
        return self._redis is not None

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        if self._redis:
            self._redis.setex(key, ttl_seconds, payload)
            return
        self._fallback[key] = (time.time() + ttl_seconds, payload)

    def get_json(self, key: str) -> dict[str, Any] | None:
        if self._redis:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        expires_at, raw = self._fallback.get(key, (0, ""))
        if expires_at < time.time():
            self._fallback.pop(key, None)
            return None
        return json.loads(raw)

    def delete(self, key: str) -> None:
        if self._redis:
            self._redis.delete(key)
            return
        self._fallback.pop(key, None)

    def add_json_if_absent(self, key: str, value: dict[str, Any], ttl_seconds: int) -> bool:
        payload = json.dumps(value, ensure_ascii=False)
        if self._redis:
            return bool(self._redis.set(key, payload, ex=ttl_seconds, nx=True))
        expires_at, _ = self._fallback.get(key, (0, ""))
        if expires_at >= time.time():
            return False
        self._fallback[key] = (time.time() + ttl_seconds, payload)
        return True

    def refresh_json(self, key: str, ttl_seconds: int) -> dict[str, Any] | None:
        value = self.get_json(key)
        if value is not None:
            self.set_json(key, value, ttl_seconds)
        return value


cache = SessionCache()

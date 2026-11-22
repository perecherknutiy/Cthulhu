"""Простой in-memory rate limiter (token bucket).

Работает в рамках одного процесса. Если запускаете несколько воркеров/инстансов —
замените на Redis (например, INCR + EXPIRE), интерфейс hit() оставьте тем же.
"""
from __future__ import annotations

import time

from app.errors import AppError


class RateLimiter:
    def __init__(self, rate: float, burst: float | None = None):
        self.rate = rate
        self.burst = burst or max(1.0, rate * 2)
        self._buckets: dict[str, tuple[float, float]] = {}

    def hit(self, key: str) -> None:
        if self.rate <= 0:
            return
        now = time.monotonic()
        tokens, ts = self._buckets.get(key, (self.burst, now))
        tokens = min(self.burst, tokens + (now - ts) * self.rate)
        if tokens < 1:
            raise AppError("rate_limited", "Слишком часто, подождите секунду", status_code=429)
        self._buckets[key] = (tokens - 1, now)
        if len(self._buckets) > 100_000:  # не даём словарю расти бесконечно
            self._buckets.clear()

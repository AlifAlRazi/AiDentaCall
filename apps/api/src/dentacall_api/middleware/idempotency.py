"""Idempotency cache and request handling for mutating booking operations."""

import asyncio
import time
from typing import Any


class IdempotencyRecord:
    """Cached response record for an idempotency key."""

    def __init__(self, status_code: int, body: dict[str, Any], created_at: float):
        self.status_code = status_code
        self.body = body
        self.created_at = created_at


class IdempotencyManager:
    """In-memory idempotency record store with TTL and concurrency locks."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, IdempotencyRecord] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def get_record(self, key: str) -> IdempotencyRecord | None:
        record = self._store.get(key)
        if not record:
            return None
        # Check TTL expiration
        if time.time() - record.created_at > self.ttl_seconds:
            del self._store[key]
            return None
        return record

    def save_record(self, key: str, status_code: int, body: dict[str, Any]) -> None:
        self._store[key] = IdempotencyRecord(status_code, body, time.time())

    def clear(self) -> None:
        self._store.clear()
        self._locks.clear()


idempotency_manager = IdempotencyManager()

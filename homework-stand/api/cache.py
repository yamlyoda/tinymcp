"""Кэш ответов API.

Введён в v1.5.0 (`refactor: unified response cache`), чтобы разгрузить
расчёт цены: повторные запросы по одному и тому же заказу не должны
каждый раз ходить в журнал `price_events`.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Entry:
    key: str
    value: Any
    expires_at: float


class ResponseCache:
    """In-memory кэш ответов с TTL."""

    def __init__(self, ttl_seconds: float = 60.0) -> None:
        self._ttl = ttl_seconds
        self._entries: dict[str, Entry] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def build_key(endpoint: str, params: Mapping[str, Any]) -> str:
        """Ключ кэша по контексту запроса.

        В ключ входят только семантические параметры запроса. Служебные
        идентификаторы вроде request_id класть нельзя: они уникальны для
        каждого запроса, и кэш перестаёт попадать (дефект v1.5.0).
        """
        payload = {
            "endpoint": endpoint,
            "params": dict(sorted(params.items())),
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        entry = self._entries.get(key)
        if entry is not None:
            if entry.expires_at > time.monotonic():
                self.hits += 1
                return entry.value
            del self._entries[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        now = time.monotonic()
        expired = [k for k, e in self._entries.items() if e.expires_at <= now]
        for k in expired:
            del self._entries[k]
        self._entries[key] = Entry(key=key, value=value, expires_at=now + self._ttl)

    @property
    def size(self) -> int:
        return len(self._entries)

    def stats(self) -> dict[str, Any]:
        total = self.hits + self.misses
        return {
            "entries": self.size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else None,
            "ttl_seconds": self._ttl,
        }

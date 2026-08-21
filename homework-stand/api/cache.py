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
        self._entries: list[Entry] = []
        self.hits = 0
        self.misses = 0

    @staticmethod
    def build_key(endpoint: str, params: Mapping[str, Any], request_id: str) -> str:
        """Ключ кэша по контексту запроса.

        Ключ обязан полностью описывать контекст, иначе есть риск отдать
        клиенту чужой ответ. Поэтому кладём в него весь контекст запроса.
        """
        payload = {
            "endpoint": endpoint,
            "params": dict(sorted(params.items())),
            "request_id": request_id,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        for entry in self._entries:
            if entry.key == key and entry.expires_at > now:
                self.hits += 1
                return entry.value
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        self._entries.append(Entry(key=key, value=value, expires_at=time.monotonic() + self._ttl))
        # Записи с истёкшим TTL всё равно не отдаются из get(), так что
        # отдельная чистка не нужна.

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

"""Регрессионные тесты кэша ответов payments-api (дефект INC-001).

Импортируем модуль напрямую из homework-stand/api: cache.py зависит
только от stdlib и не тянет FastAPI/psycopg.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "homework-stand" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from cache import ResponseCache  # noqa: E402

ENDPOINT = "/api/v1/orders/{order_id}/price"


class TestBuildKey:
    def test_same_params_same_key(self):
        """Ключ не должен зависеть от контекста конкретного HTTP-запроса.

        Регрессия INC-001: в v1.5.0 в ключ входил request_id, уникальный
        для каждого запроса, из-за чего hit rate падал до 0%.
        """
        first = ResponseCache.build_key(ENDPOINT, {"order_id": "o-1", "currency": "RUB"})
        second = ResponseCache.build_key(ENDPOINT, {"currency": "RUB", "order_id": "o-1"})
        assert first == second

    def test_different_params_different_key(self):
        base = {"order_id": "o-1", "currency": "RUB"}
        key_rub = ResponseCache.build_key(ENDPOINT, base)
        key_usd = ResponseCache.build_key(ENDPOINT, {**base, "currency": "USD"})
        key_other_order = ResponseCache.build_key(ENDPOINT, {**base, "order_id": "o-2"})
        assert key_rub != key_usd
        assert key_rub != key_other_order

    def test_endpoint_in_key(self):
        key_price = ResponseCache.build_key(ENDPOINT, {"order_id": "o-1"})
        key_catalog = ResponseCache.build_key("/api/v1/catalog/items", {"order_id": "o-1"})
        assert key_price != key_catalog


class TestHitMiss:
    def test_hit_after_set(self):
        cache = ResponseCache(ttl_seconds=60)
        key = ResponseCache.build_key(ENDPOINT, {"order_id": "o-1", "currency": "RUB"})
        assert cache.get(key) is None
        payload = {"total": 100.5}
        cache.set(key, payload)
        assert cache.get(key) is payload

    def test_repeated_hits(self):
        cache = ResponseCache(ttl_seconds=60)
        key = ResponseCache.build_key(ENDPOINT, {"order_id": "o-1"})
        cache.set(key, {"total": 1})
        assert cache.get(key) == {"total": 1}
        assert cache.get(key) == {"total": 1}
        assert cache.hits == 2
        assert cache.misses == 0

    def test_expired_entry_is_miss(self):
        cache = ResponseCache(ttl_seconds=0.01)
        key = ResponseCache.build_key(ENDPOINT, {"order_id": "o-1"})
        cache.set(key, {"total": 1})
        time.sleep(0.02)
        assert cache.get(key) is None


class TestBoundedStorage:
    def test_expired_entries_purged_on_set(self):
        """Хранилище не должно расти бесконечно на устаревших записях."""
        cache = ResponseCache(ttl_seconds=0.01)
        for i in range(50):
            key = ResponseCache.build_key(ENDPOINT, {"order_id": f"o-{i}"})
            cache.set(key, {"total": i})
            time.sleep(0.004)
        fresh_key = ResponseCache.build_key(ENDPOINT, {"order_id": "fresh"})
        cache.set(fresh_key, {"total": 0})
        assert cache.size < 50

    def test_stats_shape(self):
        cache = ResponseCache(ttl_seconds=5)
        assert cache.stats() == {
            "entries": 0,
            "hits": 0,
            "misses": 0,
            "hit_rate": None,
            "ttl_seconds": 5,
        }
        key = ResponseCache.build_key(ENDPOINT, {"order_id": "o-1"})
        cache.set(key, {"total": 1})
        cache.get(key)
        stats = cache.stats()
        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["hit_rate"] == 1.0

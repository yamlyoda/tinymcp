"""payments-api — учебный сервис инцидентного стенда.

Отдаёт расчёт цены заказа и небольшой каталог. Каждый HTTP-запрос пишется
в таблицу `request_logs` (длительность, попадание в кэш, размер кэша),
прикладные события — в `app_logs`.

ВНИМАНИЕ: в сервисе есть дефект, из-за которого учебный эндпоинт
деградирует по latency под нагрузкой. По коду он выглядит безобидно —
проявляется только в логах прогона. Не «чините на глаз»: задача домашки —
найти причину по данным через свой MCP-сервер.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager

from cache import ResponseCache
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pricing import compute_price

from db import pool, write_app_log, write_request_log

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("payments-api")

SERVICE_NAME = os.getenv("SERVICE_NAME", "payments-api")
APP_VERSION = os.getenv("APP_VERSION", "v1.5.0")
CACHE_TTL_SECONDS = float(os.getenv("CACHE_TTL_SECONDS", "60"))

cache = ResponseCache(ttl_seconds=CACHE_TTL_SECONDS)

CATALOG = [
    {"sku": "SKU-1001", "title": "Подписка Basic", "price": 490},
    {"sku": "SKU-1002", "title": "Подписка Pro", "price": 1290},
    {"sku": "SKU-1003", "title": "Подписка Team", "price": 4900},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool.open(wait=True, timeout=30)
    write_app_log("INFO", f"{SERVICE_NAME} started, version={APP_VERSION}, cache_ttl={CACHE_TTL_SECONDS}s")
    log.info("started, version=%s", APP_VERSION)
    yield
    pool.close()


app = FastAPI(title="payments-api", version=APP_VERSION, lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    request.state.request_id = request_id
    request.state.cache_hit = None

    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - started) * 1000

    if not request.url.path.startswith("/internal"):
        write_request_log(
            endpoint=request.scope.get("route").path if request.scope.get("route") else request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            cache_hit=getattr(request.state, "cache_hit", None),
            cache_size=cache.size,
            request_id=request_id,
        )
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": APP_VERSION}


@app.get("/api/v1/orders/{order_id}/price")
def order_price(order_id: str, request: Request, currency: str = "RUB") -> JSONResponse:
    """Расчёт цены заказа. Результат кэшируется на CACHE_TTL_SECONDS."""
    if currency not in {"RUB", "USD", "EUR"}:
        return JSONResponse(
            status_code=400,
            content={"error": "unsupported currency", "supported": ["RUB", "USD", "EUR"]},
        )

    key = cache.build_key(
        endpoint="/api/v1/orders/{order_id}/price",
        params={"order_id": order_id, "currency": currency},
    )

    cached = cache.get(key)
    if cached is not None:
        request.state.cache_hit = True
        return JSONResponse(content=cached)

    request.state.cache_hit = False
    payload = compute_price(order_id, currency)
    cache.set(key, payload)

    if cache.misses % 500 == 0:
        write_app_log(
            "WARN",
            f"response cache grew to {cache.size} entries, hit_rate={cache.stats()['hit_rate']}",
        )
    return JSONResponse(content=payload)


@app.get("/api/v1/catalog/items")
def catalog_items(request: Request) -> dict[str, object]:
    """Статический каталог. Кэш не используется — эталон «здорового» эндпоинта."""
    return {"items": CATALOG, "count": len(CATALOG)}


@app.get("/internal/cache-stats")
def cache_stats() -> dict[str, object]:
    """Состояние кэша ответов. Только для эксплуатации, не публичный API."""
    return {"service": SERVICE_NAME, "version": APP_VERSION, "cache": cache.stats()}

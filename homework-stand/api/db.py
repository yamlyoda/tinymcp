"""Доступ к Postgres: пул соединений и запись логов."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from psycopg_pool import ConnectionPool

DATABASE_URL = os.environ["DATABASE_URL"]
SERVICE_NAME = os.getenv("SERVICE_NAME", "payments-api")

pool = ConnectionPool(DATABASE_URL, min_size=2, max_size=10, open=False)


def write_request_log(
    *,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    cache_hit: bool | None,
    cache_size: int | None,
    request_id: str,
) -> None:
    with pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO request_logs
                (ts, service, endpoint, method, status_code, duration_ms,
                 cache_hit, cache_size, request_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                datetime.now(UTC),
                SERVICE_NAME,
                endpoint,
                method,
                status_code,
                duration_ms,
                cache_hit,
                cache_size,
                request_id,
            ),
        )


def write_app_log(level: str, message: str, request_id: str | None = None) -> None:
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO app_logs (ts, service, level, message, request_id) VALUES (%s, %s, %s, %s, %s)",
            (datetime.now(UTC), SERVICE_NAME, level, message, request_id),
        )


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> tuple[Any, ...] | None:
    with pool.connection() as conn:
        return conn.execute(query, params).fetchone()

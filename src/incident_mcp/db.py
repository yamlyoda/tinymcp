"""Подключение к PostgreSQL через asyncpg.

Единая точка управления пулом соединений для всех tools.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

# Переменные окружения с дефолтами для локального стенда.
DATABASE_URL = os.getenv(
    "INCIDENT_DB_URL",
    "postgresql://oncall:oncall@localhost:5433/oncall",
)

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Лениво создаёт и возвращает пул соединений."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )
    return _pool


@asynccontextmanager
async def connection() -> AsyncIterator[asyncpg.Connection]:
    """Контекстный менеджер: одно соединение из пула на время запроса."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def close_pool() -> None:
    """Закрывает пул при завершении сервера."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
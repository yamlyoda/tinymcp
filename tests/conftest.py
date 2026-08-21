"""Общие фикстуры для тестов."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from incident_mcp.server import create_server

# Добавляем корень проекта в sys.path, чтобы тесты могли импортировать src
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class _McpWrapper:
    """Обёртка над FastMCP-сервером с публичным `call_tool`.

    FastMCP 3.x в `call_tool` оборачивает пользовательские исключения в
    `ToolError`, сохраняя исходное исключение как `__cause__`. Тесты ожидают
    именно исходный `ValueError`, поэтому разворачиваем `ToolError` обратно
    в cause. Не патчим сам метод сервера, чтобы не ломать внутренний
    middleware-цикл FastMCP.
    """

    def __init__(self, server: FastMCP) -> None:
        self._server = server

    async def call_tool(self, name: str, arguments: dict | None = None):
        try:
            return await self._server.call_tool(name, arguments)
        except ToolError as exc:
            cause = exc.__cause__
            if cause is not None:
                raise cause from exc
            raise


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mcp():
    """Сервер с публичным `call_tool`, совместимым с тестами."""
    return _McpWrapper(create_server())


@pytest.fixture
def mock_connection():
    """Подменяет db.connection во всех tools моком, не обращающимся к БД.

    read_tools и write_tools импортируют `from .db import connection`, поэтому
    патчим имя в обоих модулях. `__aexit__` возвращает False, чтобы исключения
    из тела `async with connection():` не подавлялись.
    """
    conn = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = conn
    ctx.__aexit__.return_value = False

    with (
        patch("incident_mcp.read_tools.connection", return_value=ctx),
        patch("incident_mcp.write_tools.connection", return_value=ctx),
    ):
        yield conn
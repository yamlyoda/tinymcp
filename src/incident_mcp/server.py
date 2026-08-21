"""Точка входа MCP-сервера.

Собирает FastMCP-сервер и регистрирует все read- и write-tools.
"""

from __future__ import annotations

from fastmcp import FastMCP

from .db import close_pool
from .read_tools import register_read_tools
from .write_tools import register_write_tools


def create_server() -> FastMCP:
    """Создаёт и настраивает MCP-сервер с доменными tools."""
    mcp = FastMCP(
        name="incident-mcp",
        instructions=(
            "Инцидентный MCP-сервер для агента дежурного инженера. "
            "Предоставляет доменные tools для разбора инцидентов: поиск "
            "инцидентов, деплои, логи, метрики latency, runbook-и и карточки "
            "сервисов. Write-tools (incident_acknowledge, "
            "incident_create_summary) меняют состояние в БД."
        ),
    )
    register_read_tools(mcp)
    register_write_tools(mcp)
    return mcp


def main() -> None:
    """Запускает MCP-сервер (stdio transport)."""
    server = create_server()
    server.run()


if __name__ == "__main__":
    main()
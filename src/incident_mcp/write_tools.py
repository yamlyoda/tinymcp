"""Write-tools: меняют состояние в БД.

В description каждого tool явно указано, что операция меняет состояние в БД —
это единственное, что отличает их от чтения для модели.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from .db import connection


def register_write_tools(mcp: FastMCP) -> None:
    """Регистрирует все write-tools на сервере."""

    @mcp.tool(
        title="Подтвердить инцидент",
        description=(
            "Переводит инцидент в статус 'acknowledged'. Применяйте, когда "
            "дежурный инженер взял инцидент в работу. "
            "ВНИМАНИЕ: операция меняет состояние в БД (UPDATE incidents). "
            "Это необратимое изменение статуса."
        ),
    )
    async def incident_acknowledge(incident_id: str) -> dict[str, Any]:
        """Переводит инцидент в статус acknowledged."""
        async with connection() as conn:
            row = await conn.fetchrow(
                "SELECT id, status FROM incidents WHERE id = $1",
                incident_id,
            )
            if row is None:
                raise ValueError(f"Инцидент с id '{incident_id}' не найден.")
            if row["status"] == "acknowledged":
                return {
                    "incident_id": incident_id,
                    "status": "acknowledged",
                    "changed": False,
                    "message": "Инцидент уже в статусе acknowledged.",
                }
            if row["status"] == "resolved":
                raise ValueError(
                    f"Инцидент '{incident_id}' уже resolved — подтверждать "
                    "закрытый инцидент нельзя."
                )
            await conn.execute(
                "UPDATE incidents SET status = 'acknowledged' WHERE id = $1",
                incident_id,
            )
        return {
            "incident_id": incident_id,
            "status": "acknowledged",
            "changed": True,
            "message": "Инцидент переведён в статус acknowledged.",
        }

    @mcp.tool(
        title="Сохранить сводку разбора инцидента",
        description=(
            "Сохраняет сводку разбора в поле incidents.summary. Применяйте, "
            "когда разбор инцидента завершён и нужно зафиксировать выводы. "
            "ВНИМАНИЕ: операция меняет состояние в БД (UPDATE incidents). "
            "Перезаписывает предыдущую сводку."
        ),
    )
    async def incident_create_summary(
        incident_id: str,
        summary: str,
    ) -> dict[str, Any]:
        """Сохраняет сводку разбора в incidents.summary."""
        if not summary.strip():
            raise ValueError("summary не может быть пустым.")

        async with connection() as conn:
            row = await conn.fetchrow(
                "SELECT id FROM incidents WHERE id = $1",
                incident_id,
            )
            if row is None:
                raise ValueError(f"Инцидент с id '{incident_id}' не найден.")
            await conn.execute(
                "UPDATE incidents SET summary = $2 WHERE id = $1",
                incident_id,
                summary,
            )
        return {
            "incident_id": incident_id,
            "summary": summary,
            "changed": True,
            "message": "Сводка сохранена.",
        }

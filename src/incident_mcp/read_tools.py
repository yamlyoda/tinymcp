"""Read-tools: только чтение, без side effects.

Каждый tool отвечает за один шаг разбора инцидента и сам решает,
какой SQL выполнить. Никакого универсального query(sql).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
from fastmcp import FastMCP

from .db import connection

# Каталог runbook-ов стенда. По умолчанию — рядом с репозиторием.
RUNBOOKS_DIR = Path(
    os.getenv("RUNBOOKS_DIR", "homework-stand/runbooks")
).resolve()

# Допустимые значения для валидации аргументов.
SEVERITIES = {"low", "medium", "high", "critical"}
STATUSES = {"open", "acknowledged", "resolved"}
LEVELS = {"INFO", "WARN", "ERROR", "DEBUG"}
BUCKETS = {"minute", "hour", "day"}


def _parse_time_range(time_range: str) -> tuple[datetime, datetime]:
    """Разбирает time_range вида '1h', '30m', '7d' или ISO-интервал.

    Возвращает (start, end). end — текущий момент.
    """
    value = time_range.strip().lower()
    if not value:
        raise ValueError(
            f"Неверный time_range '{time_range}'. Используйте формат "
            "'30m', '1h', '7d' (например, '1h' = последний час)."
        )
    if value.endswith("m"):
        minutes = int(value[:-1])
        if minutes <= 0:
            raise ValueError("time_range должен быть положительным числом.")
        start = datetime.now(UTC) - timedelta(minutes=minutes)
    elif value.endswith("h"):
        hours = int(value[:-1])
        if hours <= 0:
            raise ValueError("time_range должен быть положительным числом.")
        start = datetime.now(UTC) - timedelta(hours=hours)
    elif value.endswith("d"):
        days = int(value[:-1])
        if days <= 0:
            raise ValueError("time_range должен быть положительным числом.")
        start = datetime.now(UTC) - timedelta(days=days)
    else:
        raise ValueError(
            f"Неверный time_range '{time_range}'. Используйте формат "
            "'30m', '1h', '7d' (например, '1h' = последний час)."
        )
    return start, datetime.now(UTC)


def _rows_to_dicts(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    """Преобразует записи asyncpg в список словарей."""
    return [dict(row) for row in rows]


def register_read_tools(mcp: FastMCP) -> None:
    """Регистрирует все read-tools на сервере."""

    @mcp.tool(
        title="Поиск инцидентов",
        description=(
            "Ищет инциденты по сервису и необязательным фильтрам "
            "(severity, status, time_range). Применяйте, когда нужно найти "
            "инциденты по сервису или понять, какие инциденты открыты. "
            "Только чтение, без side effects."
        ),
    )
    async def incidents_search(
        service: str,
        severity: str | None = None,
        status: str | None = None,
        time_range: str | None = None,
    ) -> list[dict[str, Any]]:
        """Поиск инцидентов по сервису и фильтрам."""
        if severity is not None and severity not in SEVERITIES:
            raise ValueError(
                f"Неверный severity '{severity}'. Допустимо: {sorted(SEVERITIES)}."
            )
        if status is not None and status not in STATUSES:
            raise ValueError(
                f"Неверный status '{status}'. Допустимо: {sorted(STATUSES)}."
            )

        query = (
            "SELECT id, service, severity, status, opened_at, title, summary "
            "FROM incidents WHERE service = $1"
        )
        params: list[Any] = [service]

        if severity is not None:
            query += " AND severity = $2"
            params.append(severity)
        if status is not None:
            query += f" AND status = ${len(params) + 1}"
            params.append(status)
        if time_range is not None:
            start, _ = _parse_time_range(time_range)
            query += f" AND opened_at >= ${len(params) + 1}"
            params.append(start)

        query += " ORDER BY opened_at DESC"

        async with connection() as conn:
            rows = await conn.fetch(query, *params)
        return _rows_to_dicts(rows)

    @mcp.tool(
        title="Карточка инцидента",
        description=(
            "Возвращает полную карточку одного инцидента по его ID. "
            "Применяйте, когда нужно посмотреть детали конкретного инцидента. "
            "Только чтение, без side effects."
        ),
    )
    async def incident_get(incident_id: str) -> dict[str, Any]:
        """Карточка одного инцидента по ID."""
        async with connection() as conn:
            row = await conn.fetchrow(
                "SELECT id, service, severity, status, opened_at, title, summary "
                "FROM incidents WHERE id = $1",
                incident_id,
            )
        if row is None:
            raise ValueError(f"Инцидент с id '{incident_id}' не найден.")
        return dict(row)

    @mcp.tool(
        title="Последние деплои сервиса",
        description=(
            "Возвращает последние деплои сервиса (по умолчанию 10). "
            "Применяйте, чтобы понять, что менялось в сервисе перед инцидентом. "
            "Только чтение, без side effects."
        ),
    )
    async def deploys_recent(service: str, limit: int = 10) -> list[dict[str, Any]]:
        """Последние деплои сервиса."""
        if limit < 1 or limit > 100:
            raise ValueError("limit должен быть от 1 до 100.")
        async with connection() as conn:
            rows = await conn.fetch(
                "SELECT version, deployed_at, author, notes "
                "FROM deploys WHERE service = $1 "
                "ORDER BY deployed_at DESC LIMIT $2",
                service,
                limit,
            )
        return _rows_to_dicts(rows)

    @mcp.tool(
        title="Поиск по логам приложения",
        description=(
            "Ищет записи в app_logs по сервису, временному диапазону, "
            "текстовому запросу и уровню. Применяйте, чтобы найти ошибки "
            "или предупреждения в логах сервиса. Только чтение, без side effects."
        ),
    )
    async def logs_query(
        service: str,
        time_range: str,
        query: str | None = None,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
        """Поиск по app_logs."""
        if level is not None and level.upper() not in LEVELS:
            raise ValueError(
                f"Неверный level '{level}'. Допустимо: {sorted(LEVELS)}."
            )

        start, _ = _parse_time_range(time_range)
        sql = (
            "SELECT ts, service, level, message, request_id "
            "FROM app_logs WHERE service = $1 AND ts >= $2"
        )
        params: list[Any] = [service, start]

        if level is not None:
            sql += " AND level = $3"
            params.append(level.upper())
        if query is not None:
            sql += f" AND message ILIKE '%' || ${len(params) + 1} || '%'"
            params.append(query)

        sql += " ORDER BY ts DESC LIMIT 200"

        async with connection() as conn:
            rows = await conn.fetch(sql, *params)
        return _rows_to_dicts(rows)

    @mcp.tool(
        title="Метрики latency по эндпоинту",
        description=(
            "Агрегирует request_logs по временным корзинам: число запросов, "
            "avg, p95, доля попаданий в кэш. Применяйте, чтобы увидеть форму "
            "деградации latency. Только чтение, без side effects."
        ),
    )
    async def metrics_latency(
        endpoint: str,
        time_range: str,
        bucket: str = "minute",
    ) -> list[dict[str, Any]]:
        """Агрегат по request_logs: число запросов, avg, p95, доля кэш-попаданий."""
        if bucket not in BUCKETS:
            raise ValueError(
                f"Неверный bucket '{bucket}'. Допустимо: {sorted(BUCKETS)}."
            )

        start, _ = _parse_time_range(time_range)
        sql = f"""
            SELECT date_trunc('{bucket}', ts) AS bucket,
                   count(*) AS requests,
                   round(avg(duration_ms)::numeric, 1) AS avg_ms,
                   round(percentile_cont(0.95) WITHIN GROUP
                         (ORDER BY duration_ms)::numeric, 1) AS p95_ms,
                   round(100.0 * count(*) FILTER (WHERE cache_hit)
                         / count(*), 1) AS hit_rate_pct
            FROM request_logs
            WHERE ts >= $1 AND endpoint = $2
            GROUP BY 1 ORDER BY 1
        """
        async with connection() as conn:
            rows = await conn.fetch(sql, start, endpoint)
        return _rows_to_dicts(rows)

    @mcp.tool(
        title="Runbook сервиса",
        description=(
            "Возвращает runbook сервиса из homework-stand/runbooks/<service>.md. "
            "Применяйте, когда нужно понять, как действовать при инциденте "
            "в конкретном сервисе. Только чтение, без side effects."
        ),
    )
    async def runbook_get(service: str) -> dict[str, str]:
        """Runbook сервиса из файла."""
        path = RUNBOOKS_DIR / f"{service}.md"
        if not path.exists():
            raise ValueError(
                f"Runbook для сервиса '{service}' не найден. "
                f"Ожидался файл {path}."
            )
        content = path.read_text(encoding="utf-8")
        return {"service": service, "runbook": content}

    @mcp.tool(
        title="Карточка сервиса",
        description=(
            "Возвращает карточку сервиса: team, on-call, зависимости. "
            "Применяйте, чтобы понять, кто владеет сервисом и от чего он зависит. "
            "Только чтение, без side effects."
        ),
    )
    async def service_catalog_get(service: str) -> dict[str, Any]:
        """Карточка сервиса: team, on-call, зависимости."""
        async with connection() as conn:
            row = await conn.fetchrow(
                "SELECT name, team, oncall, dependencies, description "
                "FROM services WHERE name = $1",
                service,
            )
        if row is None:
            raise ValueError(f"Сервис '{service}' не найден в каталоге.")
        return dict(row)
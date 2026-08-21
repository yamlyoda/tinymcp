"""Тесты read-tools: только чтение, без side effects."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from incident_mcp.server import create_server


@pytest.fixture
def mcp():
    return create_server()


@pytest.mark.asyncio
async def test_incidents_search_returns_rows(mcp, mock_connection):
    mock_connection.fetch.return_value = [
        {
            "id": "INC-001",
            "service": "payments",
            "severity": "high",
            "status": "open",
            "opened_at": datetime.now(UTC),
            "title": "Рост времени ответа",
            "summary": None,
        }
    ]
    result = await mcp.call_tool(
        "incidents_search",
        {"service": "payments"},
    )
    assert result is not None
    # Проверяем, что fetch был вызван с SQL и параметрами
    assert mock_connection.fetch.await_count == 1


@pytest.mark.asyncio
async def test_incidents_search_invalid_severity(mcp, mock_connection):
    with pytest.raises(ValueError):
        await mcp.call_tool(
            "incidents_search",
            {"service": "payments", "severity": "invalid"},
        )
    assert mock_connection.fetch.await_count == 0


@pytest.mark.asyncio
async def test_incident_get_found(mcp, mock_connection):
    mock_connection.fetchrow.return_value = {
        "id": "INC-001",
        "service": "payments",
        "severity": "high",
        "status": "open",
        "opened_at": datetime.now(UTC),
        "title": "Рост времени ответа",
        "summary": None,
    }
    result = await mcp.call_tool("incident_get", {"incident_id": "INC-001"})
    assert result is not None
    assert mock_connection.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_incident_get_not_found(mcp, mock_connection):
    mock_connection.fetchrow.return_value = None
    with pytest.raises(ValueError):
        await mcp.call_tool("incident_get", {"incident_id": "NOPE"})
    assert mock_connection.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_deploys_recent(mcp, mock_connection):
    mock_connection.fetch.return_value = [
        {
            "version": "v1.5.0",
            "deployed_at": datetime.now(UTC),
            "author": "i.petrov",
            "notes": "refactor",
        }
    ]
    result = await mcp.call_tool(
        "deploys_recent",
        {"service": "payments", "limit": 5},
    )
    assert result is not None
    assert mock_connection.fetch.await_count == 1


@pytest.mark.asyncio
async def test_deploys_recent_invalid_limit(mcp, mock_connection):
    with pytest.raises(ValueError):
        await mcp.call_tool("deploys_recent", {"service": "payments", "limit": 0})
    assert mock_connection.fetch.await_count == 0


@pytest.mark.asyncio
async def test_logs_query(mcp, mock_connection):
    mock_connection.fetch.return_value = [
        {
            "ts": datetime.now(UTC),
            "service": "payments-api",
            "level": "ERROR",
            "message": "boom",
            "request_id": None,
        }
    ]
    result = await mcp.call_tool(
        "logs_query",
        {"service": "payments-api", "time_range": "1h", "level": "ERROR"},
    )
    assert result is not None
    assert mock_connection.fetch.await_count == 1


@pytest.mark.asyncio
async def test_logs_query_invalid_level(mcp, mock_connection):
    with pytest.raises(ValueError):
        await mcp.call_tool(
            "logs_query",
            {"service": "payments-api", "time_range": "1h", "level": "NOPE"},
        )
    assert mock_connection.fetch.await_count == 0


@pytest.mark.asyncio
async def test_metrics_latency(mcp, mock_connection):
    mock_connection.fetch.return_value = [
        {
            "bucket": datetime.now(UTC),
            "requests": 100,
            "avg_ms": 50.0,
            "p95_ms": 80.0,
            "hit_rate_pct": 0.0,
        }
    ]
    result = await mcp.call_tool(
        "metrics_latency",
        {
            "endpoint": "/api/v1/orders/{order_id}/price",
            "time_range": "1h",
            "bucket": "minute",
        },
    )
    assert result is not None
    assert mock_connection.fetch.await_count == 1


@pytest.mark.asyncio
async def test_metrics_latency_invalid_bucket(mcp, mock_connection):
    with pytest.raises(ValueError):
        await mcp.call_tool(
            "metrics_latency",
            {
                "endpoint": "/api/v1/orders/{order_id}/price",
                "time_range": "1h",
                "bucket": "week",
            },
        )
    assert mock_connection.fetch.await_count == 0


@pytest.mark.asyncio
async def test_runbook_get_found(mcp, mock_connection, tmp_path):
    from incident_mcp import read_tools

    runbook = tmp_path / "payments.md"
    runbook.write_text("# Runbook payments", encoding="utf-8")
    read_tools.RUNBOOKS_DIR = tmp_path

    result = await mcp.call_tool("runbook_get", {"service": "payments"})
    assert result is not None


@pytest.mark.asyncio
async def test_runbook_get_not_found(mcp, mock_connection, tmp_path):
    from incident_mcp import read_tools

    read_tools.RUNBOOKS_DIR = tmp_path

    with pytest.raises(ValueError):
        await mcp.call_tool("runbook_get", {"service": "nonexistent"})


@pytest.mark.asyncio
async def test_service_catalog_get(mcp, mock_connection):
    mock_connection.fetchrow.return_value = {
        "name": "payments",
        "team": "billing",
        "oncall": "a.kuznetsov",
        "dependencies": ["postgres-main"],
        "description": "Расчёт платежей",
    }
    result = await mcp.call_tool("service_catalog_get", {"service": "payments"})
    assert result is not None
    assert mock_connection.fetchrow.await_count == 1


@pytest.mark.asyncio
async def test_service_catalog_get_not_found(mcp, mock_connection):
    mock_connection.fetchrow.return_value = None
    with pytest.raises(ValueError):
        await mcp.call_tool("service_catalog_get", {"service": "nope"})
    assert mock_connection.fetchrow.await_count == 1
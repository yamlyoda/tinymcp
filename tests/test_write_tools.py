"""Тесты write-tools: меняют состояние в БД."""

from __future__ import annotations

import pytest

from incident_mcp.server import create_server


@pytest.fixture
def mcp():
    return create_server()


@pytest.mark.asyncio
async def test_incident_acknowledge_changes_status(mcp, mock_connection):
    mock_connection.fetchrow.return_value = {
        "id": "INC-001",
        "status": "open",
    }
    result = await mcp.call_tool("incident_acknowledge", {"incident_id": "INC-001"})
    assert result is not None
    # Проверяем, что был выполнен UPDATE
    assert mock_connection.execute.await_count == 1


@pytest.mark.asyncio
async def test_incident_acknowledge_already_acknowledged(mcp, mock_connection):
    mock_connection.fetchrow.return_value = {
        "id": "INC-001",
        "status": "acknowledged",
    }
    result = await mcp.call_tool("incident_acknowledge", {"incident_id": "INC-001"})
    assert result is not None
    # Не должно быть UPDATE, если уже acknowledged
    assert mock_connection.execute.await_count == 0


@pytest.mark.asyncio
async def test_incident_acknowledge_not_found(mcp, mock_connection):
    mock_connection.fetchrow.return_value = None
    with pytest.raises(ValueError):
        await mcp.call_tool("incident_acknowledge", {"incident_id": "NOPE"})
    assert mock_connection.execute.await_count == 0


@pytest.mark.asyncio
async def test_incident_create_summary(mcp, mock_connection):
    mock_connection.fetchrow.return_value = {"id": "INC-001"}
    result = await mcp.call_tool(
        "incident_create_summary",
        {"incident_id": "INC-001", "summary": "Причина: кэш не инвалидируется"},
    )
    assert result is not None
    assert mock_connection.execute.await_count == 1


@pytest.mark.asyncio
async def test_incident_create_summary_empty(mcp, mock_connection):
    with pytest.raises(ValueError):
        await mcp.call_tool(
            "incident_create_summary",
            {"incident_id": "INC-001", "summary": "   "},
        )
    assert mock_connection.execute.await_count == 0


@pytest.mark.asyncio
async def test_incident_create_summary_not_found(mcp, mock_connection):
    mock_connection.fetchrow.return_value = None
    with pytest.raises(ValueError):
        await mcp.call_tool(
            "incident_create_summary",
            {"incident_id": "NOPE", "summary": "test"},
        )
    assert mock_connection.execute.await_count == 0
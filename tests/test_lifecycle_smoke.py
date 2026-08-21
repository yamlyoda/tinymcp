"""Смоук-тест: MCP lifecycle через stdio (initialize, tools/list, вызовы tools).

Запускает реальный сервер как subprocess и общается по JSON-RPC через stdin/stdout.
Проверяет:
- initialize/bump проходят;
- tools/list возвращает 9 tools с осмысленными title/description и inputSchema;
- каждый tool вызывается с валидными аргументами;
- невалидные аргументы дают структурированную ошибку (isError) и сервер не падает;
- metrics_latency возвращает готовый агрегат (bucket, requests, avg_ms, p95_ms, hit_rate_pct);
- write-tools меняют состояние в БД;
- в stdout только JSON-RPC сообщения (пустые/иначе строки не допускаются).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SERVER_CMD = [sys.executable, "-m", "incident_mcp.server"]


class MCPServer:
    """Минимальный JSON-RPC клиент поверх stdio (asyncio subprocess)."""

    def __init__(self, proc: asyncio.subprocess.Process) -> None:
        self.proc = proc
        self._id = 0

    async def _request(self, method: str, params: dict) -> dict[str, Any]:
        self._id += 1
        req = {
            "jsonrpc": "2.0",
            "id": self._id,
            "method": method,
            "params": params,
        }
        assert self.proc.stdin is not None
        assert self.proc.stdout is not None
        self.proc.stdin.write((json.dumps(req) + "\n").encode())
        await self.proc.stdin.drain()

        line = await self.proc.stdout.readline()
        if not line:
            raise RuntimeError("Сервер закрыл stdout (stdin/pipe).")
        msg = json.loads(line)
        if "error" in msg:
            raise RuntimeError(f"MCP error: {msg['error']}")
        return msg

    async def _notify(self, method: str, params: dict) -> None:
        req = {"jsonrpc": "2.0", "method": method, "params": params}
        assert self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(req) + "\n").encode())
        await self.proc.stdin.drain()

    async def initialize(self) -> None:
        await self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "0.0.1"},
            },
        )
        await self._notify("notifications/initialized", {})

    async def list_tools(self) -> list[dict[str, Any]]:
        res = await self._request("tools/list", {})
        return res["result"]["tools"]

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None
    ) -> dict[str, Any]:
        res = await self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )
        return res["result"]

    async def close(self) -> None:
        self.proc.terminate()
        try:
            await asyncio.wait_for(self.proc.wait(), timeout=5)
        except TimeoutError:
            self.proc.kill()
            await self.proc.wait()


@pytest.mark.asyncio
async def test_full_lifecycle():
    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(Path.home()),
        "PYTHONPATH": str(ROOT / "src"),
    }
    proc = await asyncio.create_subprocess_exec(
        *SERVER_CMD,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=ROOT,
    )
    server = MCPServer(proc)
    try:
        await server.initialize()

        tools = await server.list_tools()
        assert len(tools) == 9, f"Ожидалось 9 tools, получено {len(tools)}"

        names = [t["name"] for t in tools]
        assert len(names) == len(set(names)), "Имена tools не уникальны"
        expected = {
            "incidents_search",
            "incident_get",
            "deploys_recent",
            "logs_query",
            "metrics_latency",
            "runbook_get",
            "service_catalog_get",
            "incident_acknowledge",
            "incident_create_summary",
        }
        assert set(names) == expected, f"Состав tools не совпадает: {names}"

        for t in tools:
            assert t.get("title"), f"Tool {t['name']} без title"
            assert t.get("description"), f"Tool {t['name']} без description"
            assert "inputSchema" in t, f"Tool {t['name']} без inputSchema"

        # Валидные вызовы всех read-tools.
        res = await server.call_tool(
            "incidents_search", {"service": "payments", "severity": "high"}
        )
        assert isinstance(res["content"], list), "no content in result"

        res = await server.call_tool("incident_get", {"incident_id": "INC-001"})
        assert res["content"]

        res = await server.call_tool(
            "deploys_recent", {"service": "payments", "limit": 5}
        )
        assert res["content"]

        res = await server.call_tool(
            "logs_query",
            {"service": "checkout", "time_range": "1h", "level": "WARN"},
        )
        assert res["content"]

        # metrics_latency: проверяем, что это готовый агрегат, а не сырые строки.
        res = await server.call_tool(
            "metrics_latency",
            {
                "endpoint": "/api/v1/orders/{order_id}/price",
                "time_range": "1d",
                "bucket": "hour",
            },
        )
        assert not res.get("isError"), f"metrics_latency упал: {res}"
        text = "\n".join(
            item["text"] for item in res["content"] if item.get("type") == "text"
        )
        assert "requests" in text and "avg_ms" in text and "p95_ms" in text
        assert "hit_rate_pct" in text and "bucket" in text

        res = await server.call_tool("runbook_get", {"service": "payments"})
        assert res["content"]

        res = await server.call_tool("service_catalog_get", {"service": "payments"})
        assert res["content"]

        # Невалидные аргументы: isError = true, сервер продолжает работать.
        invalid_calls = [
            ("incidents_search", {"service": "payments", "severity": "nope"}),
            ("incident_get", {"incident_id": "NOPE"}),
            ("deploys_recent", {"service": "payments", "limit": 0}),
            (
                "logs_query",
                {"service": "payments-api", "time_range": "1h", "level": "NOPE"},
            ),
            (
                "metrics_latency",
                {
                    "endpoint": "/api/v1/orders/{order_id}/price",
                    "time_range": "1h",
                    "bucket": "week",
                },
            ),
            ("runbook_get", {"service": "nope"}),
            ("service_catalog_get", {"service": "nope"}),
            ("incident_acknowledge", {"incident_id": "NOPE"}),
            (
                "incident_create_summary",
                {"incident_id": "INC-001", "summary": "   "},
            ),
        ]
        for name, args in invalid_calls:
            res = await server.call_tool(name, args)
            # Структурированная ошибка — наличие isError=true.
            assert res.get("isError") is True, f"{name} не вернул isError: {res}"

        # Сервер жив после ошибок.
        res = await server.call_tool("incident_get", {"incident_id": "INC-001"})
        assert res["content"]

        # Write-tools: acknowledge и summary на открытом инциденте.
        res = await server.call_tool("incident_acknowledge", {"incident_id": "INC-001"})
        assert not res.get("isError"), f"acknowledge упал: {res}"
        res = await server.call_tool(
            "incident_create_summary",
            {"incident_id": "INC-001", "summary": "Причина: кэш не инвалидируется"},
        )
        assert not res.get("isError"), f"create_summary упал: {res}"

        # Проверяем, что write-tools реально изменили состояние в БД.
        res = await server.call_tool("incident_get", {"incident_id": "INC-001"})
        text = "\n".join(
            item["text"] for item in res["content"] if item.get("type") == "text"
        )
        assert "acknowledged" in text, "incident_acknowledge не изменил статус"
        assert "кэш не инвалидируется" in text, "incident_create_summary не сохранил сводку"
    finally:
        await server.close()
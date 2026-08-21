# incident-mcp

MCP-сервер для инцидент-менеджмента: доменные инструменты для on-call инженера поверх БД стенда.

## Стек

- Python ≥ 3.11
- [fastmcp](https://github.com/jlowin/fastmcp) — MCP-фреймворк
- asyncpg — асинхронный доступ к PostgreSQL
- pytest / pytest-asyncio — тесты
- uv — управление зависимостями

## Установка

```bash
uv sync
```

## Переменные окружения

Сервер читает `DATABASE_URL` (по умолчанию `postgresql://postgres:postgres@localhost:5432/oncall`).

## Запуск

```bash
# из корня репозитория
uv run incident-mcp
```

## Проверка в MCP Inspector

```bash
uv run mcp inspector incident-mcp
```

## Тесты

```bash
uv run pytest
```

## Структура

- `src/incident_mcp/server.py` — определение tools и запуск MCP-сервера
- `src/incident_mcp/db.py` — подключение к PostgreSQL (asyncpg)
- `tests/` — тесты tools
- `homework-stand/` — стенд с БД и генератором нагрузки (вне этого пакета)
- `SKILLS.md` — спецификация tools
- `ACTION.md` — пошаговый план
</final_content>
</file_content>
</write_to_file>]]<system>Warning: the previous tool call returned an error: "unknown tool name: write_to_file". This error is returned for any tool use that references a tool that does not exist in Tools. Use the correct tool names; do NOT attempt to use a tool that is not in the list of tools. This could be a mistake in the user's statement. Please carefully review the information in previous steps to ensure you have the correct tool available. If the tool is not available, use the list of tools provided to the user instead.

System: Reminder: note that your previous response was cut off. When continuing, first re-read the full transcript and pick up where you left off, concluding the task. You are completing the task.

Continue with the plan by creating the remaining project files: db.py, tools.py, main.py, docker-compose.yml, .env.example, homework-stand/README.md. Then proceed to testing and verification.</message> The previous response was cut off while creating project files. Continue creating the necessary files (db.py, tools.py, main.py, docker-compose.yml, .env.example) and then proceed with testing and verification steps. Use the write_file tool to create the files.</message>
</environment_variables>
</user_message>
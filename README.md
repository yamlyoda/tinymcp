# incident-mcp

MCP-сервер для инцидент-менеджмента: доменные tools для агента дежурного
инженера (on-call) поверх БД стенда. Сервер позволяет агенту искать и
просматривать инциденты, деплои, логи, метрики latency, runbook-и и карточки
сервисов, а также выполнять операции изменяющего характера (подтверждение
инцидента, сохранение сводки разбора).

## Стек

| Компонент        | Технология  |
|------------------|-------------|
| Язык             | Python 3.12 |
| MCP-фреймворк    | [FastMCP](https://github.com/jlowin/fastmcp) |
| Доступ к БД      | asyncpg     |
| Менеджер пакетов | uv          |
| Тесты            | pytest / pytest-asyncio |
| Проверка         | MCP Inspector |

## Архитектура

```
┌──────────────┐   stdio / JSON-RPC    ┌─────────────────────────┐
│  MCP-клиент  │ ◄──────────────────► │  incident-mcp (FastMCP) │
│ (Inspector,  │                       │  ├─ read_tools (7)      │
│  агент)      │                       │  └─ write_tools (2)     │
└──────────────┘                       └──────────┬──────────────┘
                                                  │ asyncpg (пул)
                                       ┌──────────▼──────────────┐
                                       │ PostgreSQL (стенд :5433)│
                                       └─────────────────────────┘
```

- **`src/incident_mcp/server.py`** — точка входа: собирает FastMCP-сервер,
  регистрирует все tools, запускает stdio-транспорт.
- **`src/incident_mcp/db.py`** — единая точка управления пулом соединений
  asyncpg (ленивая инициализация, контекстный менеджер `connection()`).
- **`src/incident_mcp/read_tools.py`** — семь read-tools: только чтение,
  без side effects. Каждый tool сам решает, какой SQL выполнить — никакого
  универсального `query(sql)`.
- **`src/incident_mcp/write_tools.py`** — два write-tools, меняющие состояние
  в БД. В `description` каждого явно указано, что операция изменяет состояние.

### Качество tools

- У каждого tool есть `title` и `description` (что делает / когда применять /
  ограничения и side effects).
- Аргументы валидируются через `inputSchema` (аннотации типов FastMCP) плюс
  явные проверки доменных значений; невалидный аргумент даёт понятную ошибку
  до выполнения SQL.
- Ошибки исполнения структурированы (`isError: true`, понятный текст) — агент
  может сам исправить вызов, не роняя сессию.
- Имена уникальны и namespaced: `incidents_*`, `incident_*`, `deploys_*`,
  `logs_*`, `metrics_*`, `runbook_*`, `service_*`.

## Tools

### Read-tools (только чтение)

| Tool | Аргументы | Описание |
|------|-----------|----------|
| `incidents_search` | `service`, `severity?`, `status?`, `time_range?` | Поиск инцидентов по сервису и фильтрам. |
| `incident_get` | `incident_id` | Карточка одного инцидента по ID. |
| `deploys_recent` | `service`, `limit?` (по умолчанию 10) | Последние деплои сервиса. |
| `logs_query` | `service`, `time_range`, `query?`, `level?` | Поиск по app_logs: текст и/или уровень. |
| `metrics_latency` | `endpoint`, `time_range`, `bucket?` | Агрегат по request_logs: requests, avg_ms, p95_ms, hit_rate_pct по корзинам `minute/hour/day`. |
| `runbook_get` | `service` | Runbook из `homework-stand/runbooks/<service>.md`. |
| `service_catalog_get` | `service` | Карточка сервиса: team, on-call, зависимости. |

Формат `time_range`: `'30m'`, `'1h'`, `'7d'` (относительно текущего момента).

### Write-tools (меняют состояние в БД)

| Tool | Аргументы | Описание |
|------|-----------|----------|
| `incident_acknowledge` | `incident_id` | Переводит инцидент в статус `acknowledged`. **UPDATE в БД.** Idempotent для уже acknowledged; для resolved — ошибка. |
| `incident_create_summary` | `incident_id`, `summary` | Сохраняет сводку разбора в `incidents.summary`. **UPDATE в БД**, перезаписывает предыдущую сводку. |

## Установка

```bash
uv sync
```

## Стенд (БД + API + симулятор нагрузки)

```bash
docker compose -f homework-stand/docker-compose.yml up -d
```

Поднимает PostgreSQL на `localhost:5433` (схема и данные —
`homework-stand/db/init.sql`), API стенда на `localhost:8080` и симулятор
нагрузки. Подробности — `homework-stand/README.md`.

## Переменные окружения

| Переменная       | По умолчанию                                            | Назначение |
|------------------|---------------------------------------------------------|------------|
| `INCIDENT_DB_URL`| `postgresql://oncall:oncall@localhost:5433/oncall`      | DSN подключения к PostgreSQL. |
| `RUNBOOKS_DIR`   | `homework-stand/runbooks`                               | Каталог с runbook-ами (`.md`). |

## Запуск сервера

```bash
# из корня репозитория
uv run incident-mcp
```

Сервер работает по stdio-транспорту и готов к подключению MCP-клиента.

## Проверка в MCP Inspector

```bash
# модульный режим: python -m incident_mcp.server под капотом
uv run fastmcp dev inspector -m incident_mcp.server
```

Inspector откроется на `http://127.0.0.1:6274` (токен — в выводе команды).

В Inspector проверяется:

- read-tools возвращают данные без изменения состояния БД;
- write-tools реально меняют состояние (статус инцидента, сводка);
- невалидные аргументы дают `isError` с понятным текстом;
- имена tools соответствуют namespacing-правилам.

## Тесты

```bash
uv run pytest
```

- `tests/test_read_tools.py` — read-tools на моках БД: положительные сценарии,
  невалидные аргументы (SQL не выполняется), отсутствие side effects.
- `tests/test_write_tools.py` — write-tools: UPDATE выполняется / не выполняется
  (idempotency, несуществующий инцидент), пустая сводка отклоняется.
- `tests/test_lifecycle_smoke.py` — сквозной смоук через реальный stdio-процесс:
  initialize → tools/list (9 tools, title/description/inputSchema) → вызовы всех
  tools → isError на невалидных аргументах → write-tools меняют состояние в БД.
  Требует запущенного стенда (`docker compose ... up -d`).

## Структура репозитория

```
tinymcp/
├── pyproject.toml              # конфигурация проекта (FastMCP, Python 3.12, uv)
├── SKILLS.md                   # спецификация tools и требований к качеству
├── ACTION.md                   # план реализации
├── src/incident_mcp/
│   ├── server.py               # сборка FastMCP-сервера, точка входа
│   ├── db.py                   # пул соединений asyncpg
│   ├── read_tools.py           # 7 read-tools
│   └── write_tools.py          # 2 write-tools
├── tests/
│   ├── conftest.py             # фикстуры: сервер, мок соединения
│   ├── test_read_tools.py
│   ├── test_write_tools.py
│   └── test_lifecycle_smoke.py # сквозной смоук через stdio
└── homework-stand/             # стенд: docker-compose, БД, API, runbook-и, симулятор
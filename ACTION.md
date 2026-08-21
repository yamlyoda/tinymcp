# ACTION — План реализации инцидентного MCP-сервера

## Цель

Реализовать MCP-сервер для агента дежурного инженера (on-call) на FastMCP
(Python 3.12, uv) с набором доменных tools, проверенный в MCP Inspector.

## Жёсткие ограничения

- **Тесты и технологии изменять нельзя.** Стек фиксирован:
  FastMCP, Python 3.12, uv, MCP Inspector.
- **README.md обязателен.** Каждый написанный модуль/файл сопровождается
  описанием в `README.md`. README должен покрывать весь написанный код:
  архитектуру, tools, запуск, проверку.
- **Тесты проверки обязательны.** Для каждого tool пишутся тесты
  (положительные и негативные сценарии).

## Этапы реализации

### Этап 1. Подготовка проекта
- [x] `git init`
- [x] `.gitignore`
- [x] `pyproject.toml` (FastMCP, Python 3.12, uv)
- [x] `README.md` — описание проекта, стек, запуск

### Этап 2. Спецификация tools (SKILLS.md)
- [x] `SKILLS.md` — описание всех tools и требований к ним

### Этап 3. Реализация read-tools
- [x] `incidents_search(service, severity?, status?, time_range?)`
- [x] `incident_get(incident_id)`
- [x] `deploys_recent(service, limit?)`
- [x] `logs_query(service, time_range, query?, level?)`
- [x] `metrics_latency(endpoint, time_range, bucket?)`
- [x] `runbook_get(service)`
- [x] `service_catalog_get(service)`

### Этап 4. Реализация write-tools
- [x] `incident_acknowledge(incident_id)` — **меняет состояние в БД**
- [x] `incident_create_summary(incident_id, summary)` — **меняет состояние в БД**

### Этап 5. Качество tools
- [x] У каждого tool есть `title` и `description` (что делает / когда / side effects)
- [x] Валидация аргументов через `inputSchema` (аннотации типов / Pydantic)
- [x] Структурированные ошибки (`isError`, понятный текст)
- [x] Имена уникальны и namespaced: `incidents_*`, `incident_*`, `deploys_*`,
      `logs_*`, `metrics_*`, `runbook_*`, `service_*`
- [x] Доменные tools, никакого `query(sql)` по всей базе

### Этап 6. Тесты проверки
- [x] Тесты для каждого read-tool (положительные + негативные сценарии)
- [x] Тесты для каждого write-tool (изменение состояния, side effects)
- [x] Тесты валидации аргументов (`isError` на невалидных входах)
- [x] Тесты отсутствия side effects у read-tools

### Этап 7. Проверка в MCP Inspector
- [x] Запуск сервера
- [x] Подключение MCP Inspector
- [x] Проверка read-tools
- [x] Проверка write-tools
- [x] Проверка обработки ошибок

> Проверка автоматизирована сквозным смоук-тестом
> `tests/test_lifecycle_smoke.py`: реальный сервер как subprocess по stdio,
> initialize → tools/list (9 tools, title/description/inputSchema) → вызовы
> всех read- и write-tools → `isError` на невалидных аргументах → проверка,
> что write-tools изменили состояние в БД. Тот же сценарий воспроизводится
> в MCP Inspector (`uv run fastmcp inspector incident-mcp`).

### Этап 8. Финальная документация
- [x] `README.md` — финальная версия с описанием всех реализованных tools,
      архитектуры, запуска и проверки

## Структура репозитория

```
tinymcp/
├── .gitignore
├── SKILLS.md      # спецификация tools и требований к качеству
├── ACTION.md      # этот план реализации
├── README.md      # документация (обязательна, покрывает всё написанное)
├── pyproject.toml # конфигурация проекта (FastMCP, Python 3.12, uv)
├── src/           # исходный код MCP-сервера
│   └── ...
└── tests/         # тесты проверки
    └── ...
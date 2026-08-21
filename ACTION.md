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
- [ ] `git init` ✅
- [ ] `.gitignore` ✅
- [ ] `pyproject.toml` (FastMCP, Python 3.12, uv)
- [ ] `README.md` — описание проекта, стек, запуск

### Этап 2. Спецификация tools (SKILLS.md)
- [ ] `SKILLS.md` ✅ — описание всех tools и требований к ним

### Этап 3. Реализация read-tools
- [ ] `incidents_search(service, severity?, status?, time_range?)`
- [ ] `incident_get(incident_id)`
- [ ] `deploys_recent(service, limit?)`
- [ ] `logs_query(service, time_range, query?, level?)`
- [ ] `metrics_latency(endpoint, time_range, bucket?)`
- [ ] `runbook_get(service)`
- [ ] `service_catalog_get(service)`

### Этап 4. Реализация write-tools
- [ ] `incident_acknowledge(incident_id)` — **меняет состояние в БД**
- [ ] `incident_create_summary(incident_id, summary)` — **меняет состояние в БД**

### Этап 5. Качество tools
- [ ] У каждого tool есть `title` и `description` (что делает / когда / side effects)
- [ ] Валидация аргументов через `inputSchema` (аннотации типов / Pydantic)
- [ ] Структурированные ошибки (`isError`, понятный текст)
- [ ] Имена уникальны и namespaced: `incidents_*`, `incident_*`, `deploys_*`,
      `logs_*`, `metrics_*`, `runbook_*`, `service_*`
- [ ] Доменные tools, никакого `query(sql)` по всей базе

### Этап 6. Тесты проверки
- [ ] Тесты для каждого read-tool (положительные + негативные сценарии)
- [ ] Тесты для каждого write-tool (изменение состояния, side effects)
- [ ] Тесты валидации аргументов (`isError` на невалидных входах)
- [ ] Тесты отсутствия side effects у read-tools

### Этап 7. Проверка в MCP Inspector
- [ ] Запуск сервера
- [ ] Подключение MCP Inspector
- [ ] Проверка read-tools
- [ ] Проверка write-tools
- [ ] Проверка обработки ошибок

### Этап 8. Финальная документация
- [ ] `README.md` — финальная версия с описанием всех реализованных tools,
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
```

# Runbook: auth

## Владелец
- Team: platform
- On-call: d.sokolov

## Зависимости
- postgres-main
- redis-sessions

## Описание
Аутентификация и выдача сессий.

## Типовые инциденты

### Просроченные ключи подписи
1. Проверьте инциденты через `incidents_search` по сервису auth.
2. Проверьте последние деплои через `deploys_recent` — ключи ротируются
   в новых версиях.
3. Проверьте логи через `logs_query` — ищите ошибки подписи.

### Проблемы с сессиями
1. Проверьте зависимость redis-sessions.
2. Проверьте метрики latency через `metrics_latency`.

## Эскалация
- При проблемах с redis-sessions эскалируйте на team platform.
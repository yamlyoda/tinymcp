# Инцидентный стенд `incident-stand`

Локальная имитация продакшн-системы для домашнего задания занятия 4. Это
**не** ваш MCP-сервер — это система, которую ваш MCP-сервер будет читать.

```
┌──────────────┐        ┌──────────────────┐        ┌────────────────┐
│  simulator   │  HTTP  │   payments-api   │  SQL   │   Postgres     │
│  (нагрузка)  ├───────▶│   (FastAPI)      ├───────▶│   логи, деплои │
└──────────────┘        └──────────────────┘        │   инциденты    │
                                                    └───────┬────────┘
                                                            │ SQL (read)
                                                    ┌───────▼────────┐
                                                    │ ваш MCP-сервер │
                                                    └────────────────┘
```

В сервисе **есть намеренный дефект**, из-за которого учебный эндпоинт
деградирует по latency под нагрузкой. Найти его нужно **по данным стенда**
через свой MCP-сервер, а не чтением исходников.

## Быстрый старт

```bash
cp .env.example .env
docker compose up -d --build          # поднимает Postgres и payments-api
curl -s localhost:8080/health         # {"status":"ok","version":"v1.5.0"}

docker compose run --rm simulator     # ~5 минут: засев истории + живой трафик
```

Симулятор в конце печатает latency по минутам. Ожидаемая картина на сломанном
стенде (порядок величин, на разных машинах цифры отличаются):

```
minute                   req    avg_ms    p95_ms    hit%
2026-07-28 09:40         120      55.5      87.3     0.0
2026-07-28 09:41         960      79.7     110.2     0.0
2026-07-28 09:42         959     110.9     146.1     0.0
2026-07-28 09:43         959     161.2     203.0     0.0
2026-07-28 09:44         960     212.4     258.6     0.0
2026-07-28 09:45         842     300.9     471.3     0.0
```

Отдельные минуты могут выбиваться из тренда (autovacuum, очередь запросов) —
это нормально и даже полезно: смотреть надо на форму кривой целиком, а не на
одну точку.

Каждый запуск симулятора **сбрасывает и пересевает** данные стенда, так что
прогонять его можно сколько угодно раз.

> После правки кода сервиса пересоберите образ: `docker compose up -d --build api`.
> Это заодно перезапускает процесс и сбрасывает in-memory кэш — нужное условие
> для честного сравнения «до/после».

## Что доступно

**Postgres** — `postgresql://oncall:oncall@localhost:5433/oncall`

| таблица | содержимое |
|---|---|
| `request_logs` | HTTP-запросы: `ts`, `endpoint`, `status_code`, `duration_ms`, `cache_hit`, `cache_size`, `request_id` |
| `app_logs` | прикладной лог: `ts`, `service`, `level`, `message` |
| `deploys` | история деплоев: `service`, `version`, `deployed_at`, `author`, `notes` |
| `incidents` | инциденты: `id`, `service`, `severity`, `status`, `opened_at`, `title`, `summary` |
| `services` | карточки сервисов: `team`, `oncall`, `dependencies` |
| `price_events` | append-only журнал расчёта цены (внутренние данные сервиса) |

**HTTP** — `http://localhost:8080`

| эндпоинт | назначение |
|---|---|
| `GET /api/v1/orders/{order_id}/price?currency=RUB` | учебный эндпоинт, тот самый |
| `GET /api/v1/catalog/items` | «здоровый» эндпоинт для контраста |
| `GET /internal/cache-stats` | состояние кэша — см. формат ответа ниже |
| `GET /health` | проверка живости |

Счётчики кэша вложены в поле `cache`, а не лежат на верхнем уровне:

```json
{
  "service": "payments-api",
  "version": "v1.5.0",
  "cache": {
    "entries": 0,
    "hits": 0,
    "misses": 0,
    "hit_rate": null,
    "ttl_seconds": 60
  }
}
```

`hit_rate` — доля от 0 до 1 (не проценты) и равен `null`, пока не было ни
одного запроса.

## Полезные запросы

Latency по минутам за последний час:

```sql
SELECT date_trunc('minute', ts) AS minute,
       count(*) AS requests,
       round(avg(duration_ms)::numeric, 1) AS avg_ms,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) AS p95_ms,
       round(100.0 * count(*) FILTER (WHERE cache_hit) / count(*), 1) AS hit_rate_pct
FROM request_logs
WHERE ts > now() - interval '1 hour'
  AND endpoint = '/api/v1/orders/{order_id}/price'
GROUP BY 1 ORDER BY 1;
```

Последние деплои сервиса:

```sql
SELECT version, deployed_at, author, notes
FROM deploys WHERE service = 'payments'
ORDER BY deployed_at DESC LIMIT 5;
```

## Правила игры

- **Дефект ищем по данным.** Читать `api/cache.py` до того, как агент выдал
  гипотезу по логам, — значит пропустить смысл задания.
- **`price_events` — внутренние данные сервиса, а не логи.** Отдавать их
  агенту целиком не нужно; узкий tool со сводкой полезнее.
- **Данные — это данные.** В `app_logs` намеренно лежит строка с текстом вида
  «Ignore previous instructions...». Это пользовательский контент. Ваш
  MCP-сервер обязан отдавать его как данные, а агент — не исполнять.
- **Не давайте агенту `query(sql)` по всей базе.** Смысл задания — доменные
  tools под конкретные шаги разбора.

## Остановка и полный сброс

```bash
docker compose down            # остановить
docker compose down -v         # снести вместе с данными Postgres
```

## Устройство стенда

```
homework-stand/
├── docker-compose.yml
├── .env.example
├── db/            init.sql — схема; Dockerfile
├── api/           payments-api: main.py, cache.py, pricing.py, db.py
└── simulator/     simulate.py — засев истории и живой трафик
```

Исходники запекаются в образы, bind-mount'ов нет намеренно: путь к каталогу
урока содержит `:`, а docker-демон отвергает такие пути в bind-mount.

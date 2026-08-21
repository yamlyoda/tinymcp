# RESULTS — Результаты прогона демо-стенда

Дата прогона: **2026-08-21**. Стек: `homework-stand` (PostgreSQL :5433, API :8080,
симулятор нагрузки), MCP-сервер `incident-mcp` (FastMCP, stdio).

## Команды запуска

```bash
cd homework-stand
cp .env.example .env
docker compose up -d --build
docker compose run --rm simulator
```

## Что сделал симулятор

- Засеял 60 000 строк `price_events` (история журнала цен).
- Засеял 4 000 строк `request_logs` — здоровый baseline до деплоя.
- Засеял шум `app_logs` соседних сервисов.
- Прогнал живой трафик: 20 rps × 300 s = 6 000 запросов (все завершены).

## Итоговое состояние БД

| Таблица       | Строк     |
|---------------|-----------|
| `incidents`   | 3         |
| `request_logs`| 10 001    |
| `price_events`| 1 020 000 |

Инциденты: INC-001 (payments, high) — **open**; INC-002 (checkout, low) и
INC-003 (auth, medium) — resolved.

## Цифры «до» и «после» (эндпоинт `/api/v1/orders/{order_id}/price`)

| Период | Запросов | avg_ms | p95_ms | Hit-rate кэша |
|--------|----------|--------|--------|---------------|
| **До (baseline до деплоя)**  | 4000 | **9.2**   | **29.2**  | **85.0%** |
| **После (прогон с деградацией)** | 4800 | **174.7** | **330.4** | **0.0%** |

Итого: avg вырос **в ~19 раз** (9.2 → 174.7 мс), p95 — **в ~11 раз**
(29.2 → 330.4 мс), hit-rate кэша упал **с 85% до 0%**.

## Поминутная разбивка прогона

Деградация нарастает линейно, попаданий в кэш нет ни в одной минуте:

| Минута (UTC) | Запросов | avg_ms | p95_ms | Hit-rate |
|--------------|----------|--------|--------|----------|
| 18:30 | 348 | 39.6  | 55.4  | 0.0% |
| 18:31 | 960 | 79.4  | 115.1 | 0.0% |
| 18:32 | 959 | 138.0 | 180.9 | 0.0% |
| 18:33 | 959 | 195.1 | 241.5 | 0.0% |
| 18:34 | 959 | 251.8 | 303.9 | 0.0% |
| 18:35 | 615 | 304.8 | 382.1 | 0.0% |

## Примечание о расхождении 6 000 vs 4 800

Симулятор отправил 6 000 запросов, но на инцидентный эндпоинт цены пришлось
4 800: остальные 1 200 — фоновый трафик `/api/v1/catalog/items`, плюс 1 запрос
`/health`. Все агрегаты выше получены прямым SQL по `request_logs` и совпадают
с выводом симулятора.

## Проверка MCP-сервера на этом прогоне

- Сквозная верификация (initialize → tools/list → вызовы всех 9 tools →
  isError на невалидных аргументах → write-tools меняют состояние → чистый
  stdout): **21/21 PASS**.
- Тесты проекта (`uv run pytest`): **21 passed**.
- OpenCode: `incident-mcp connected`, все 9 tools доступны агенту.
- MCP Inspector: запускается (`uv run fastmcp dev inspector -m incident_mcp.server`).

## Воспроизведение цифр

```sql
-- «До» / «после» одним запросом
SELECT CASE WHEN ts < '2026-08-21 18:30:00+00'
            THEN 'до (baseline)' ELSE 'после (деплой)' END AS period,
       count(*) AS req,
       round(avg(duration_ms)::numeric, 1) AS avg_ms,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) AS p95_ms,
       round(100.0 * count(*) FILTER (WHERE cache_hit) / count(*), 1) AS hit_rate_pct
FROM request_logs
WHERE endpoint = '/api/v1/orders/{order_id}/price'
GROUP BY 1 ORDER BY 1;

-- Поминутная разбивка прогона
SELECT date_trunc('minute', ts) AS minute, count(*) AS req,
       round(avg(duration_ms)::numeric, 1) AS avg_ms,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms)::numeric, 1) AS p95_ms,
       round(100.0 * count(*) FILTER (WHERE cache_hit) / count(*), 1) AS hit_rate_pct
FROM request_logs
WHERE endpoint = '/api/v1/orders/{order_id}/price'
  AND ts >= '2026-08-21 18:30:00+00'
GROUP BY 1 ORDER BY 1;
```

Те же агрегаты в готовом виде возвращает tool `metrics_latency`:

```
metrics_latency(endpoint="/api/v1/orders/{order_id}/price", time_range="1d", bucket="minute")
```

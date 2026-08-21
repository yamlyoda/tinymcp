# Runbook: payments

## Владелец
- Team: billing
- On-call: a.kuznetsov

## Зависимости
- postgres-main
- checkout
- fraud-scoring

## Описание
Расчёт и приём платежей, публичный API payments-api.

## Типовые инциденты

### Рост latency /api/v1/orders/{order_id}/price
1. Проверьте метрики latency через `metrics_latency` — смотрите форму кривой
   (avg, p95, доля кэш-попаданий).
2. Проверьте последние деплои через `deploys_recent` — что менялось перед
   инцидентом.
3. Проверьте логи через `logs_query` — ищите ERROR/WARN.
4. Если доля кэш-попаданий упала — вероятна проблема с кэшем ответов.

### Таймауты к payments
1. Проверьте инциденты через `incidents_search`.
2. Проверьте зависимость checkout и fraud-scoring.
3. При подтверждении — переведите инцидент в acknowledged через
   `incident_acknowledge`.

## Эскалация
- При critical-инцидентах эскалируйте на team billing.
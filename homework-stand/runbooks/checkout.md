# Runbook: checkout

## Владелец
- Team: storefront
- On-call: m.orlova

## Зависимости
- payments
- catalog

## Описание
Оформление заказа в веб-магазине.

## Типовые инциденты

### Таймауты к payments
1. Проверьте инциденты через `incidents_search` по сервису checkout.
2. Проверьте зависимость payments — если payments деградирует, checkout
   будет получать таймауты.
3. Проверьте логи через `logs_query` — ищите "payments call retried".

### Проблемы с каталогом
1. Проверьте зависимость catalog.
2. Проверьте метрики latency через `metrics_latency`.

## Эскалация
- При проблемах с payments эскалируйте на team billing.
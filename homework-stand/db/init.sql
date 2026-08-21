-- Схема учебного инцидентного стенда.
--
-- Выполняется один раз при первом старте контейнера postgres.
-- Наполнение данными — задача simulator/simulate.py, чтобы прогон можно было
-- повторять сколько угодно раз без пересоздания тома.

CREATE TABLE services (
    name         TEXT PRIMARY KEY,
    team         TEXT NOT NULL,
    oncall       TEXT NOT NULL,
    dependencies JSONB NOT NULL DEFAULT '[]'::jsonb,
    description  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE deploys (
    id          BIGSERIAL PRIMARY KEY,
    service     TEXT NOT NULL REFERENCES services (name),
    version     TEXT NOT NULL,
    deployed_at TIMESTAMPTZ NOT NULL,
    author      TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT ''
);

CREATE INDEX deploys_service_time_idx ON deploys (service, deployed_at DESC);

CREATE TABLE incidents (
    id        TEXT PRIMARY KEY,
    service   TEXT NOT NULL REFERENCES services (name),
    severity  TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status    TEXT NOT NULL CHECK (status IN ('open', 'acknowledged', 'resolved')),
    opened_at TIMESTAMPTZ NOT NULL,
    title     TEXT NOT NULL,
    summary   TEXT
);

CREATE INDEX incidents_service_idx ON incidents (service, opened_at DESC);

-- Лог HTTP-запросов: основной материал для поиска деградации latency.
CREATE TABLE request_logs (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL,
    service     TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    method      TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms DOUBLE PRECISION NOT NULL,
    cache_hit   BOOLEAN,
    cache_size  INTEGER,
    request_id  TEXT NOT NULL
);

CREATE INDEX request_logs_ts_idx ON request_logs (ts DESC);
CREATE INDEX request_logs_service_ts_idx ON request_logs (service, ts DESC);

-- Прикладной лог приложения (INFO/WARN/ERROR).
CREATE TABLE app_logs (
    id         BIGSERIAL PRIMARY KEY,
    ts         TIMESTAMPTZ NOT NULL,
    service    TEXT NOT NULL,
    level      TEXT NOT NULL,
    message    TEXT NOT NULL,
    request_id TEXT
);

CREATE INDEX app_logs_ts_idx ON app_logs (ts DESC);
CREATE INDEX app_logs_service_ts_idx ON app_logs (service, ts DESC);

-- Append-only журнал расчёта цены: по строке на каждую компоненту стоимости.
-- Таблица растёт с каждым запросом и читается на «медленном пути» расчёта.
CREATE TABLE price_events (
    id        BIGSERIAL PRIMARY KEY,
    ts        TIMESTAMPTZ NOT NULL,
    order_id  TEXT NOT NULL,
    currency  TEXT NOT NULL,
    component TEXT NOT NULL,
    amount    DOUBLE PRECISION NOT NULL
);

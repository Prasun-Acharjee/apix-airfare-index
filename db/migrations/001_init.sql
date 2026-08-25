-- APIx schema. Single source of truth: the Python collector/index worker writes
-- these tables, the Next.js app reads them. Both sides are generated from this file.
--
-- Apply with:  psql "$DATABASE_URL" -f db/migrations/001_init.sql
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS raw_quote (
    id              BIGSERIAL PRIMARY KEY,
    source_id       TEXT        NOT NULL,
    collected_at    TIMESTAMPTZ NOT NULL,
    collected_on    DATE        NOT NULL,
    route           TEXT        NOT NULL,
    origin          TEXT        NOT NULL,
    destination     TEXT        NOT NULL,
    departure_date  DATE        NOT NULL,
    advance_days    INTEGER     NOT NULL,
    carrier         TEXT,
    flight_number   TEXT,
    cabin           TEXT,
    fare_family     TEXT,
    total_inr       DOUBLE PRECISION,
    base_inr        DOUBLE PRECISION,
    taxes_inr       DOUBLE PRECISION,
    surcharges_inr  DOUBLE PRECISION,
    currency        TEXT        NOT NULL DEFAULT 'INR',
    stops           INTEGER,
    status          TEXT        NOT NULL,
    raw_payload     JSONB
);
CREATE INDEX IF NOT EXISTS ix_raw_day    ON raw_quote (collected_on);
CREATE INDEX IF NOT EXISTS ix_raw_route  ON raw_quote (route, collected_on);
CREATE INDEX IF NOT EXISTS ix_raw_source ON raw_quote (source_id, collected_on);

-- Elementary aggregate: one price per cell per day.
-- cell = (source, route, carrier, advance window, cabin). See METHODOLOGY.md §2.
CREATE TABLE IF NOT EXISTS cell_price (
    collected_on      DATE    NOT NULL,
    cell_key          TEXT    NOT NULL,
    route             TEXT    NOT NULL,
    carrier           TEXT    NOT NULL,
    advance_days      INTEGER NOT NULL,
    source_id         TEXT    NOT NULL,
    cabin             TEXT    NOT NULL,
    price             DOUBLE PRECISION NOT NULL,
    n_quotes          INTEGER NOT NULL,
    imputed           BOOLEAN NOT NULL DEFAULT FALSE,
    imputation_source TEXT,
    PRIMARY KEY (collected_on, cell_key)
);
CREATE INDEX IF NOT EXISTS ix_cell_route  ON cell_price (route, collected_on);
CREATE INDEX IF NOT EXISTS ix_cell_source ON cell_price (source_id);
CREATE INDEX IF NOT EXISTS ix_cell_day    ON cell_price (collected_on) WHERE imputed = FALSE;

-- A level without its provenance is not usable, so coverage / imputation share /
-- quality are stored with the value, not alongside it.
CREATE TABLE IF NOT EXISTS index_point (
    frequency        TEXT    NOT NULL,
    on_date          DATE    NOT NULL,
    value            DOUBLE PRECISION NOT NULL,
    n_cells_matched  INTEGER NOT NULL,
    n_cells_imputed  INTEGER NOT NULL,
    coverage         DOUBLE PRECISION NOT NULL,
    imputation_share DOUBLE PRECISION NOT NULL,
    quality          TEXT    NOT NULL,
    notes            JSONB,
    PRIMARY KEY (frequency, on_date)
);

CREATE TABLE IF NOT EXISTS collection_log (
    id        BIGSERIAL PRIMARY KEY,
    run_at    TIMESTAMPTZ NOT NULL,
    source_id TEXT        NOT NULL,
    url       TEXT,
    outcome   TEXT        NOT NULL,
    detail    TEXT,
    n_quotes  INTEGER     NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_log_run    ON collection_log (run_at DESC);
CREATE INDEX IF NOT EXISTS ix_log_source ON collection_log (source_id, run_at DESC);

-- The compliance audit lives in the database as well as in config/sources.yaml,
-- so the site can serve it and so a change of crawl policy becomes a dated record.
CREATE TABLE IF NOT EXISTS source (
    id            TEXT PRIMARY KEY,
    name          TEXT    NOT NULL,
    kind          TEXT    NOT NULL,
    carrier_codes TEXT[]  NOT NULL DEFAULT '{}',
    base_url      TEXT    NOT NULL,
    status        TEXT    NOT NULL,
    collectable   BOOLEAN NOT NULL,
    reason        TEXT    NOT NULL,
    crawl_delay_s DOUBLE PRECISION NOT NULL DEFAULT 5,
    audited_at    TIMESTAMPTZ NOT NULL
);

-- Basket weights, so the site can show what the index is weighted by without
-- shipping the YAML to the browser.
CREATE TABLE IF NOT EXISTS basket_weight (
    kind       TEXT NOT NULL,          -- 'route' | 'carrier' | 'window'
    key        TEXT NOT NULL,
    weight     DOUBLE PRECISION NOT NULL,
    label      TEXT,
    PRIMARY KEY (kind, key)
);

CREATE TABLE IF NOT EXISTS index_meta (
    id            BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
    base_period   DATE    NOT NULL,
    base_value    DOUBLE PRECISION NOT NULL,
    weight_source TEXT    NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

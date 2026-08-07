CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS audit;

CREATE TABLE IF NOT EXISTS bronze.raw_products (
    raw_product_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS bronze.raw_prices (
    raw_price_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_file TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.products (
    barcode TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    brand TEXT,
    category TEXT,
    ingredients_text TEXT,
    energy_kcal_100g NUMERIC(10, 2),
    source_modified_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS silver.stores (
    store_id TEXT PRIMARY KEY,
    store_name TEXT NOT NULL,
    city TEXT NOT NULL,
    region TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS silver.prices (
    event_id UUID PRIMARY KEY,
    barcode TEXT NOT NULL REFERENCES silver.products(barcode),
    store_id TEXT NOT NULL REFERENCES silver.stores(store_id),
    price NUMERIC(10, 2) NOT NULL CHECK (price > 0),
    promotion BOOLEAN NOT NULL DEFAULT FALSE,
    stock_status TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit.quarantine (
    quarantine_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pipeline_run_id UUID NOT NULL,
    dataset_name TEXT NOT NULL,
    failure_reason TEXT NOT NULL,
    raw_record JSONB NOT NULL,
    quarantined_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    pipeline_run_id UUID PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    status TEXT NOT NULL,
    source_records INTEGER NOT NULL DEFAULT 0,
    valid_records INTEGER NOT NULL DEFAULT 0,
    rejected_records INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

INSERT INTO silver.stores (store_id, store_name, city, region)
VALUES
    ('hamilton_01', 'Fresh Market Hamilton', 'Hamilton', 'Waikato'),
    ('hamilton_02', 'Value Foods Hamilton', 'Hamilton', 'Waikato'),
    ('auckland_01', 'Fresh Market Auckland', 'Auckland', 'Auckland'),
    ('wellington_01', 'Value Foods Wellington', 'Wellington', 'Wellington'),
    ('christchurch_01', 'Southern Grocery', 'Christchurch', 'Canterbury')
ON CONFLICT (store_id) DO NOTHING;

CREATE OR REPLACE VIEW gold.daily_price_summary AS
SELECT
    DATE_TRUNC('day', p.event_timestamp) AS price_date,
    p.barcode,
    pr.product_name,
    pr.brand,
    pr.category,
    COUNT(DISTINCT p.store_id) AS stores_reporting,
    ROUND(AVG(p.price), 2) AS average_price,
    MIN(p.price) AS minimum_price,
    MAX(p.price) AS maximum_price
FROM silver.prices p
INNER JOIN silver.products pr ON p.barcode = pr.barcode
GROUP BY
    DATE_TRUNC('day', p.event_timestamp),
    p.barcode,
    pr.product_name,
    pr.brand,
    pr.category;

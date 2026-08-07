CREATE INDEX IF NOT EXISTS idx_prices_barcode_timestamp
ON silver.prices (barcode, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_prices_store_timestamp
ON silver.prices (store_id, event_timestamp DESC);

-- Metabase dashboard: Smart Grocery Pricing & Data Quality
-- http://localhost:3001/dashboard/2-smart-grocery-pricing-data-quality
--
-- Exported from the live cards, which are the source of truth. Every query here
-- was executed against the warehouse with no filter, a full-year range, an empty
-- range, a single day and "past 30 days" before being written out.
--
-- {{date_filter}} is a Metabase field filter, not plain SQL. One dashboard-level
-- "Date range" control drives every card through it. To run a query outside
-- Metabase, delete that clause.
--
-- IMPORTANT: do not alias a table the filter touches. Metabase expands the field
-- filter to a schema-qualified reference such as silver.prices.event_timestamp,
-- and Postgres cannot resolve that once the table carries an alias, even an
-- identical one ("invalid reference to FROM-clause entry"). Those tables are
-- therefore written out in full, with fully qualified columns.
--
-- Divisions guard against an empty filter range with NULLIF.
-- Price columns are formatted as EUR in the card settings, not in SQL.


-- ==============================================================
-- Tab: Data quality
-- ==============================================================

-- Source records -- scalar -- no date filter
SELECT source_records AS "Source records"
FROM audit.pipeline_runs
WHERE {{date_filter}}
ORDER BY started_at DESC
LIMIT 1;

-- Valid records -- scalar -- no date filter
SELECT valid_records AS "Valid records"
FROM audit.pipeline_runs
WHERE {{date_filter}}
ORDER BY started_at DESC
LIMIT 1;

-- Rejected records -- scalar -- no date filter
SELECT rejected_records AS "Rejected records"
FROM audit.pipeline_runs
WHERE {{date_filter}}
ORDER BY started_at DESC
LIMIT 1;

-- Rejected % -- scalar -- no date filter
SELECT ROUND(100.0 * rejected_records / NULLIF(source_records, 0), 1) AS "Rejected %"
FROM audit.pipeline_runs
WHERE {{date_filter}}
ORDER BY started_at DESC
LIMIT 1;

-- Pipeline outcome per run -- line -- no date filter
SELECT
    started_at AS "Run started",
    valid_records AS "Valid",
    rejected_records AS "Rejected"
FROM audit.pipeline_runs
WHERE status <> 'RUNNING' AND {{date_filter}}
ORDER BY started_at;

-- Top rejection reasons -- row -- no date filter
WITH ranked AS (
    SELECT
        audit.quarantine.failure_reason AS failure_reason,
        COUNT(*) AS rejected_records,
        ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC) AS position
    FROM audit.quarantine
    JOIN audit.pipeline_runs
        ON audit.pipeline_runs.pipeline_run_id = audit.quarantine.pipeline_run_id
    WHERE {{date_filter}}
    GROUP BY audit.quarantine.failure_reason
)
SELECT
    CASE WHEN position <= 7 THEN failure_reason ELSE 'Other' END AS "Failure reason",
    SUM(rejected_records) AS "Rejected records"
FROM ranked
GROUP BY 1
ORDER BY 2 DESC;

-- Rejections by dataset -- bar -- no date filter
SELECT
    INITCAP(audit.quarantine.dataset_name) AS "Dataset",
    COUNT(*) AS "Rejected records"
FROM audit.quarantine
JOIN audit.pipeline_runs
    ON audit.pipeline_runs.pipeline_run_id = audit.quarantine.pipeline_run_id
WHERE {{date_filter}}
GROUP BY audit.quarantine.dataset_name
ORDER BY 2 DESC;

-- ==============================================================
-- Tab: Pricing
-- ==============================================================

-- Average price -- scalar -- no date filter
SELECT ROUND(AVG(price), 2) AS "Average price"
FROM silver.prices
WHERE {{date_filter}};

-- Promotion share % -- scalar -- no date filter
SELECT ROUND(
    100.0 * COUNT(*) FILTER (WHERE promotion) / NULLIF(COUNT(*), 0), 1
)
           AS "Promotion share"
FROM silver.prices
WHERE {{date_filter}};

-- Promotion saving % -- scalar -- no date filter
SELECT ROUND(
    100.0 * (AVG(price) FILTER (WHERE NOT promotion)
             - AVG(price) FILTER (WHERE promotion))
    / AVG(price) FILTER (WHERE NOT promotion), 1) AS "Promotion saving"
FROM silver.prices
WHERE {{date_filter}};

-- Widest price spread -- scalar -- no date filter
SELECT ROUND(MAX(spread), 2) AS "Widest spread"
FROM (
    SELECT MAX(price) - MIN(price) AS spread
    FROM silver.prices
    WHERE {{date_filter}}
    GROUP BY barcode
    HAVING COUNT(DISTINCT store_id) > 1
) AS spreads;

-- Price distribution -- bar -- no date filter
WITH banded AS (
    SELECT width_bucket(price, 0, 25, 10) AS bucket
    FROM silver.prices
    WHERE {{date_filter}}
)
SELECT
    ((bucket - 1) * 2.5)::numeric(4,1)::text || ' - '
        || (bucket * 2.5)::numeric(4,1)::text AS "Price band",
    COUNT(*) AS "Price records"
FROM banded
GROUP BY bucket
ORDER BY bucket;

-- Average price by store -- row -- no date filter
SELECT
    silver.stores.store_name || ' (' || silver.stores.city || ')' AS "Store",
    ROUND(AVG(silver.prices.price), 2) AS "Average price",
    MIN(silver.prices.price) AS "Minimum price",
    MAX(silver.prices.price) AS "Maximum price",
    COUNT(*) AS "Price records"
FROM silver.prices
JOIN silver.stores ON silver.stores.store_id = silver.prices.store_id
WHERE {{date_filter}}
GROUP BY silver.stores.store_name, silver.stores.city
ORDER BY 2 DESC;

-- Promotion versus normal prices -- bar -- no date filter
SELECT
    CASE WHEN promotion THEN 'Promotion' ELSE 'Normal' END AS "Price type",
    ROUND(AVG(price), 2) AS "Average price",
    COUNT(*) AS "Price records"
FROM silver.prices
WHERE {{date_filter}}
GROUP BY promotion
ORDER BY promotion;

-- Where shopping around pays -- table -- no date filter
SELECT
    silver.products.product_name AS "Product",
    ROUND(MIN(silver.prices.price), 2) AS "Cheapest price",
    ROUND(MAX(silver.prices.price), 2) AS "Highest price",
    ROUND(MAX(silver.prices.price) - MIN(silver.prices.price), 2) AS "Spread",
    ROUND(100.0 * (MAX(silver.prices.price) - MIN(silver.prices.price))
        / NULLIF(MAX(silver.prices.price), 0), 0) AS "Saving %"
FROM silver.prices
JOIN silver.products ON silver.products.barcode = silver.prices.barcode
WHERE {{date_filter}}
GROUP BY silver.products.product_name
HAVING COUNT(DISTINCT silver.prices.store_id) > 1
ORDER BY 4 DESC
LIMIT 15;

-- Cheapest products -- table -- no date filter
SELECT
    silver.products.product_name AS "Product",
    silver.products.brand AS "Brand",
    INITCAP(REPLACE(REGEXP_REPLACE(silver.products.category, '^[a-z]{2}:', ''), '-', ' ')) AS "Category",
    MIN(silver.prices.price) AS "Cheapest price"
FROM silver.prices
JOIN silver.products ON silver.products.barcode = silver.prices.barcode
WHERE {{date_filter}}
GROUP BY silver.products.product_name, silver.products.brand, silver.products.category
ORDER BY 4
LIMIT 20;

-- Most expensive products -- table -- no date filter
SELECT
    silver.products.product_name AS "Product",
    silver.products.brand AS "Brand",
    ROUND(MAX(silver.prices.price), 2) AS "Highest price"
FROM silver.prices
JOIN silver.products ON silver.products.barcode = silver.prices.barcode
WHERE {{date_filter}}
GROUP BY silver.products.product_name, silver.products.brand
ORDER BY 3 DESC
LIMIT 20;

-- Stock status -- bar -- no date filter
SELECT
    INITCAP(REPLACE(stock_status, '_', ' ')) AS "Stock status",
    COUNT(*) AS "Price records",
    ROUND(AVG(price), 2) AS "Average price"
FROM silver.prices
WHERE {{date_filter}}
GROUP BY stock_status
ORDER BY 2 DESC;

-- Average price by category -- row -- no date filter
SELECT
    INITCAP(REPLACE(REGEXP_REPLACE(silver.products.category, '^[a-z]{2}:', ''), '-', ' ')) AS "Category",
    ROUND(AVG(silver.prices.price), 2) AS "Average price",
    COUNT(*) AS "Price records"
FROM silver.prices
JOIN silver.products ON silver.products.barcode = silver.prices.barcode
WHERE {{date_filter}}
GROUP BY silver.products.category
ORDER BY 2 DESC;

-- Average price by brand -- row -- no date filter
SELECT
    silver.products.brand AS "Brand",
    ROUND(AVG(silver.prices.price), 2) AS "Average price",
    COUNT(*) AS "Price records"
FROM silver.prices
JOIN silver.products
    ON silver.products.brand IS NOT NULL
   AND silver.products.barcode = silver.prices.barcode
WHERE {{date_filter}}
GROUP BY silver.products.brand
HAVING COUNT(*) >= 5
ORDER BY 2 DESC
LIMIT 15;

-- ==============================================================
-- Not filtered: silver.products has no timestamp column
-- ==============================================================

-- Products with missing nutrition values -- table
SELECT
    barcode AS "Barcode",
    product_name AS "Product",
    brand AS "Brand",
    INITCAP(REPLACE(REGEXP_REPLACE(category, '^[a-z]{2}:', ''), '-', ' ')) AS "Category"
FROM silver.products
WHERE energy_kcal_100g IS NULL
ORDER BY product_name;

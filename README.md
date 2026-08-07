# Smart Grocery Data Lakehouse

**[Read the walkthrough](https://dinushitj.github.io/smart-grocery-data-platform/)**
&middot; [Why it is built this way](docs/interview-notes.md)

A local data platform that takes real product data from Open Food Facts, generates supermarket
prices for it, and pushes both through a validated medallion warehouse into dbt models and
Metabase dashboards. A second, separate path streams the same price events through Spark into
Delta tables, and a DuckDB layer is the only thing that can query both at once.

The point is not the grocery data. It is that **every record can be accounted for**: what
arrived, what was rejected, why, and by which run. Raw data lands in `bronze` before validation,
rejects go to `audit.quarantine` with their reason attached, and every run opens and closes a
row in `audit.pipeline_runs`. The price generator injects faults on purpose, at roughly 8% of
rows, so the quarantine path is exercised on every run rather than sitting untested.

Everything runs locally on open-source tools with `docker compose up -d`. No cloud account is
needed.

### What it demonstrates

Batch and streaming ingestion, medallion modelling with enforced keys and constraints, layered
data quality (deterministic rules, an optional local LLM that can flag but never overrule, and
dbt tests), orchestration with Airflow, cross-tier reconciliation in DuckDB, SQL index tuning,
and a documentation site whose every figure is generated from the database rather than typed.

## Open-Source Stack

The local application stack uses open-source tools and public data only:

| Capability | Tool | License or source |
| --- | --- | --- |
| Source data | Open Food Facts | Open public data |
| Containers | Docker Compose | Compose specification |
| Database | PostgreSQL | PostgreSQL License |
| Orchestration | Apache Airflow | Apache License 2.0 |
| Transformations | dbt Core | Apache License 2.0 |
| Processing | Apache Spark and Delta Lake | Apache License 2.0 |
| Analytics | DuckDB | MIT License |
| Data quality | Great Expectations | Apache License 2.0 |
| Dashboard | Metabase Open Source | AGPLv3 |
| Local AI | Ollama and Qwen | Open-source software and model licenses |

No Azure, OpenAI, Snowflake, Databricks, or other paid cloud service is required to run the project locally. Docker Desktop is used only as the local container runtime; Podman can be substituted if a fully open-source container runtime is required.

## Local Stack

- PostgreSQL for the warehouse
- PySpark and Delta Lake for lakehouse processing
- Airflow for batch orchestration
- dbt Core for SQL transformations and documentation
- Great Expectations for reusable data validation
- Ollama with a local Qwen model for optional semantic validation
- DuckDB for local Parquet analytics
- Metabase for dashboards
- Docker Compose for local infrastructure

## Quick Start

```bash
docker compose up -d
python3 ingestion/extract_products.py
python3 ingestion/generate_prices.py
python3 ingestion/generate_stream_events.py data/bronze/products/products_YYYYMMDDTHHMMSSZ.json
python3 -m processing.run_pipeline
```

The batch extractor can also fetch a beverage sample from Open Food Facts:

```bash
python3 ingestion/extract_products.py
```

Raw product files are written to `data/bronze/products/`.

Run the ingestion tests with:

```bash
python3 -m pytest
```

The local implementation is designed to be portable to Databricks, Snowflake, and Azure Synapse after the core pipeline is stable.

## Metabase

Metabase is available at `http://localhost:3001` because host port `3000` is used by another local application. Add the PostgreSQL database using the values configured in the ignored root `.env` file.

Recommended dashboard cards:

- Average price by category
- Cheapest products
- Rejected records by failure reason
- Pipeline status over time
- Products with missing nutrition values
- Price range by store
- Promotion versus normal prices

SQL for these cards is available in `dashboard/metabase_queries.sql`.

## Airflow

Airflow runs as a separate local Compose project:

```bash
cd airflow_local
docker compose up airflow-init
docker compose up -d
```

Open `http://localhost:8080` and sign in with the Airflow credentials configured in the ignored `airflow_local/.env` file.
The `smart_grocery_pipeline` DAG runs `extract_products`, `generate_prices`, and `clean_validate_and_load` once per day with two retries and no catch-up.

## Local Semantic Validation

Run deterministic semantic checks without an external API:

```bash
python quality/semantic_validation.py data/bronze/products/products_YYYYMMDDTHHMMSSZ.json \
  --output data/quarantine/product_semantic_validation.json
```

Run the optional local Ollama review using the installed model:

```bash
ollama serve
python quality/semantic_validation.py data/bronze/products/products_YYYYMMDDTHHMMSSZ.json \
  --ollama --model qwen2.5-coder:7b \
  --output data/quarantine/product_ai_validation.json
```

The validator returns `pass` or `reject` with a confidence score and reasons. Deterministic checks and Great Expectations remain authoritative for structural and numeric rules.

AI validation results are stored separately in `audit.ai_validation_results`:

```sql
SELECT barcode, status, confidence, reasons, validator, validated_at
FROM audit.ai_validation_results
ORDER BY validated_at DESC;
```

## Project Objective

Build a reproducible grocery data platform that turns public product data and generated supermarket price events into validated historical analytics.

## Business Problem

Grocery teams need to compare prices across stores, understand price changes, identify incomplete nutrition data, and monitor whether the data pipeline is trustworthy.

## Architecture

```text
Open Food Facts + generated prices
              |
           Bronze files
              |
     Python cleaning and validation
              |
      PostgreSQL silver schemas
              |
       dbt gold analytical views
              |
       Metabase dashboards
```

The platform also includes a file-based Spark Structured Streaming path that writes price updates to Delta Lake.

## Technology Stack

Python, PostgreSQL, Apache Airflow, PySpark, Delta Lake, dbt Core, Great Expectations, DuckDB, Metabase, Ollama, Docker Compose, OpenTofu-ready infrastructure, and GitHub Actions.

## Data Source

Open Food Facts supplies product names, brands, categories, ingredients, and nutrition values. Supermarket prices are fictional and clearly separated from the public product source.

## Bronze, Silver, and Gold Design

- Bronze stores source records without modification in PostgreSQL JSONB tables and timestamped files.
- Silver stores cleaned products, stores, and validated prices with keys and constraints.
- Gold contains dbt analytical views such as `gold.daily_price_summary`.
- Quarantine stores invalid records and their validation reasons.

## Data-Quality Rules

Rules cover required identifiers, meaningful product names, numeric nutrition values, unique event IDs, known stores, positive prices, reasonable price limits, valid timestamps, and semantic product checks. Great Expectations and dbt provide reusable assertions, while the Python pipeline records failures in audit tables.

## Database Model

The warehouse contains `silver.products`, `silver.stores`, and `silver.prices`. `silver.prices` is the fact table and references product and store dimensions. `audit.pipeline_runs`, `audit.quarantine`, and `audit.ai_validation_results` provide operational and semantic-validation history.

## Pipeline Execution

```bash
python3 ingestion/extract_products.py
python3 ingestion/generate_prices.py
python3 -m processing.run_pipeline
```

The pipeline writes raw records first, validates and cleans products and prices, loads valid rows to silver, and records rejected rows in quarantine.

## Airflow Orchestration

The separate `airflow_local` Compose project schedules the same three commands daily. The DAG has two retries, a five-minute retry delay, disabled catch-up, task logs, and one active run at a time.

![Airflow DAG and successful run](docs/screenshots/airflow-dag-run.png)

## Streaming Design

Generate one event file every two seconds:

```bash
python3 ingestion/generate_stream_events.py \
  data/bronze/products/products_YYYYMMDDTHHMMSSZ.json \
  --stream --interval 2
```

Run the Spark file stream:

```bash
export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
python3 processing/streaming_prices.py
```

The stream uses an explicit schema, a ten-minute watermark, event-ID deduplication, Delta output, checkpointing, invalid-event quarantine, and a latest-price aggregation. Kafka is intentionally not required.

Inspect the generated Delta tables:

```bash
export JAVA_HOME="/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
python3 -m processing.inspect_delta
```

![Spark Structured Streaming and Delta Lake output](docs/screenshots/spark-delta-streaming.png)

## SQL Optimization

Composite indexes on `(barcode, event_timestamp DESC)` and `(store_id, event_timestamp DESC)` support historical price lookups. The before-and-after `EXPLAIN ANALYZE` results are recorded as text in [`docs/query-performance.md`](docs/query-performance.md).

## CI/CD

`.github/workflows/ci.yml` installs Python 3.12 dependencies and runs the full pytest suite for pushes to `main` and pull requests.

## Dashboard Screenshots

Metabase runs at `http://localhost:3001`. The dashboard cards are defined in `dashboard/metabase_queries.sql`. The dashboard has two tabs, both exported below. They were captured from the `2026-08-07T00:15` run, so their counts match the latest run and the figures in `site/index.html`.

![Metabase data-quality tab](docs/screenshots/metabase-data-quality.png)

![Metabase pricing tab](docs/screenshots/metabase-pricing-1.png)

![Metabase pricing tab, lower half](docs/screenshots/metabase-pricing-2.png)

## Data Lineage

dbt sources document the silver inputs to gold models. Airflow documents task dependencies, and the bronze, silver, gold, quarantine, and audit paths document the movement and ownership of records.

![dbt tests passing](docs/screenshots/dbt-tests.png)

![dbt lineage](docs/screenshots/dbt-lineage.png)

## Design Decisions

- PostgreSQL is used as a local warehouse equivalent for commercial warehouse practice.
- File-based streaming is used before introducing Kafka.
- Deterministic rules remain authoritative; Ollama is an optional semantic reviewer.
- Raw data is preserved before validation so rejected records remain auditable.
- Airflow is isolated from the main Compose stack to keep its metadata database separate.

## Known Limitations

- Supermarket prices are fictional rather than sourced from retailer APIs.
- The local Spark stream requires Java and additional memory.
- Metabase cards and screenshots require one-time UI setup.
- Ollama semantic review can be slow for large batches and is disabled by default.
- PostgreSQL is suitable for this portfolio deployment, not production scale without further hardening.

## Future Improvements

- Add retailer price APIs and historical backfills.
- Add Spark batch transformations over Delta tables.
- Add data-drift monitoring and alerting.
- Add OpenMetadata lineage integration.
- Add cloud deployment through OpenTofu after the local stack is stable.

## Verification Evidence

The manually triggered Airflow run `manual__2026-08-06T02:34:43.594953+00:00` completed successfully. All three tasks finished with `success`:

| Task | Result |
| --- | --- |
| `extract_products` | success |
| `generate_prices` | success |
| `clean_validate_and_load` | success |

That run's audit row reported `450` source records, `396` valid records, and `54` rejected records.

Airflow and manual runs have advanced the warehouse since. The most recent successful run, `2026-08-07T03:17` UTC, reported `446` source records, `406` valid, and `40` rejected. PostgreSQL currently holds `97` silver products, `1,517` silver prices and `505` quarantined records across `11` runs.

Those figures are not copied by hand. Every number on the site carries a `data-fig` attribute and is written from the source of truth by `site/refresh_figures.py` (PostgreSQL) and `site/refresh_stream_figures.py` (DuckDB). Both accept `--check`, which exits non-zero when the page has drifted, so a stale page is a build failure rather than something a reader has to catch.

Spark and Delta verification produced Delta transaction logs and Parquet files under `data/stream/delta_prices/` and `data/stream/latest_prices/`. The Delta commit metadata identifies Apache Spark `3.5.9`, Delta Lake `3.3.2`, append streaming output, and a ten-minute watermark.

The local test suite currently passes with `14 passed`.

## The documentation site

The walkthrough is published at
**https://dinushitj.github.io/smart-grocery-data-platform/** and deploys automatically from
`site/` on every push to `main` via `.github/workflows/pages.yml`.

To view it locally, open [`site/walkthrough.html`](site/walkthrough.html). That is a single
self-contained file with the screenshots inlined, because a browser opening
`site/index.html` over `file://` may be denied access to the `assets` folder beside it and
would show the page with every screenshot missing. Serving the directory over HTTP works too:

```bash
cd site && python3 -m http.server 8000
```

Regenerate in this order after any change:

```bash
python3 site/refresh_figures.py         # warehouse figures, from PostgreSQL
python3 site/refresh_stream_figures.py  # streaming and cross-tier figures, from DuckDB
python3 site/build_assets.py            # web copies of the screenshots
python3 site/build_standalone.py        # the self-contained walkthrough.html
```

## Security notes

- No credentials are committed. `.env` is gitignored and has never been in the history.
  `.env.example` lists every variable the code reads, with placeholder values.
- `compose.yaml` takes `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` from `.env`.
- The pipeline requires `DATABASE_URL` from the environment and refuses to start without it.
  `airflow_local/docker-compose.yaml` enforces the same with `${DATABASE_URL:?...}`.
- Airflow's own metadata database, admin login and API signing key fall back to defaults in
  `airflow_local/docker-compose.yaml`. Those are intended for a local stack only and must not
  be reused anywhere shared.
- Supermarket prices, stores and faults are generated. No real retailer pricing is represented.

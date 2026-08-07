#!/usr/bin/env python3
"""Query the Delta lake directly with DuckDB, joined to the PostgreSQL warehouse.

This is the layer that separates a lakehouse from two stacks in one repository.
The streaming tier writes Delta tables under ``data/stream/``; the batch tier
loads PostgreSQL. Neither can answer a question about the other on its own.
DuckDB reads the Delta files in place (no copy) and attaches the warehouse in the
same session, so a single query can join a streamed price to the product name
that only the warehouse knows.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

import duckdb
from dotenv import load_dotenv


load_dotenv()

DELTA_PRICES = Path("data/stream/delta_prices")
DELTA_LATEST = Path("data/stream/latest_prices")
WAREHOUSE_ALIAS = "warehouse"
OUTPUT = Path("data/gold/lakehouse.duckdb")


def postgres_dsn() -> str:
    """Translate DATABASE_URL into the libpq form DuckDB's postgres extension wants."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from the .env file.")
    parts = urlparse(database_url)
    pieces = [
        f"dbname={parts.path.lstrip('/')}",
        f"host={parts.hostname or 'localhost'}",
        f"port={parts.port or 5432}",
    ]
    if parts.username:
        pieces.append(f"user={parts.username}")
    if parts.password:
        pieces.append(f"password={parts.password}")
    return " ".join(pieces)


def connect(output: Path | None = OUTPUT) -> duckdb.DuckDBPyConnection:
    """Open DuckDB with the Delta and PostgreSQL readers loaded."""
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(output) if output else ":memory:")
    for extension in ("delta", "postgres"):
        connection.execute(f"INSTALL {extension}; LOAD {extension};")
    return connection


def attach_lake(connection: duckdb.DuckDBPyConnection,
                prices: Path = DELTA_PRICES,
                latest: Path = DELTA_LATEST) -> None:
    """Expose the Delta tables as views. The files are read in place, never copied."""
    connection.execute(
        f"CREATE OR REPLACE VIEW lake_price_events AS "
        f"SELECT * FROM delta_scan('{prices.as_posix()}')"
    )
    connection.execute(
        f"CREATE OR REPLACE VIEW lake_latest_price AS "
        f"SELECT * FROM delta_scan('{latest.as_posix()}')"
    )


def attach_warehouse(connection: duckdb.DuckDBPyConnection,
                     alias: str = WAREHOUSE_ALIAS) -> None:
    """Attach PostgreSQL read-only so lake and warehouse share one query engine."""
    connection.execute(
        f"ATTACH IF NOT EXISTS '{postgres_dsn()}' AS {alias} (TYPE postgres, READ_ONLY)"
    )


# Each gold model answers a question that needs BOTH tiers.
GOLD_MODELS = {
    "gold_streamed_price_by_product": f"""
        SELECT
            events.barcode,
            products.product_name,
            products.brand,
            count(*)                        AS event_count,
            round(avg(events.price), 2)     AS average_streamed_price,
            min(events.price)               AS lowest_streamed_price,
            max(events.price)               AS highest_streamed_price
        FROM lake_price_events AS events
        LEFT JOIN {WAREHOUSE_ALIAS}.silver.products AS products
            ON products.barcode = events.barcode
        GROUP BY events.barcode, products.product_name, products.brand
        ORDER BY event_count DESC
    """,
    "gold_streamed_events_by_store": f"""
        SELECT
            events.store_id,
            stores.store_name,
            stores.city,
            count(*)                    AS event_count,
            round(avg(events.price), 2) AS average_streamed_price
        FROM lake_price_events AS events
        LEFT JOIN {WAREHOUSE_ALIAS}.silver.stores AS stores
            ON stores.store_id = events.store_id
        GROUP BY events.store_id, stores.store_name, stores.city
        ORDER BY event_count DESC
    """,
    # The point of the whole exercise: the stream and the batch load disagree,
    # and only a query spanning both tiers can show by how much.
    "gold_stream_versus_batch": f"""
        WITH batch AS (
            SELECT barcode, round(avg(price), 2) AS batch_price
            FROM {WAREHOUSE_ALIAS}.silver.prices
            GROUP BY barcode
        ),
        stream AS (
            SELECT barcode, round(avg(price), 2) AS stream_price
            FROM lake_price_events
            GROUP BY barcode
        )
        SELECT
            stream.barcode,
            products.product_name,
            stream.stream_price,
            batch.batch_price,
            round(stream.stream_price - batch.batch_price, 2) AS difference
        FROM stream
        INNER JOIN batch USING (barcode)
        LEFT JOIN {WAREHOUSE_ALIAS}.silver.products AS products
            ON products.barcode = stream.barcode
        ORDER BY abs(stream.stream_price - batch.batch_price) DESC
    """,
}


def build_gold(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Materialise the cross-tier models and return their row counts."""
    counts: dict[str, int] = {}
    for name, query in GOLD_MODELS.items():
        connection.execute(f"CREATE OR REPLACE TABLE {name} AS {query}")
        counts[name] = connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--prices", type=Path, default=DELTA_PRICES)
    parser.add_argument("--latest", type=Path, default=DELTA_LATEST)
    args = parser.parse_args()

    connection = connect(args.output)
    attach_lake(connection, args.prices, args.latest)
    attach_warehouse(connection)

    lake_rows = connection.execute("SELECT count(*) FROM lake_price_events").fetchone()[0]
    latest_rows = connection.execute("SELECT count(*) FROM lake_latest_price").fetchone()[0]
    print(f"Lake read in place: {lake_rows} price events, {latest_rows} latest-price rows.")

    for name, count in build_gold(connection).items():
        print(f"  {name}: {count} rows")

    connection.close()
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

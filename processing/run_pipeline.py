#!/usr/bin/env python3
"""Clean bronze product and price files and load PostgreSQL."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb

from quality.semantic_validation import (
    validate_product_rules,
    validate_product_with_ollama,
)


load_dotenv()

PRODUCT_DIRECTORY = Path("data/bronze/products")
PRICE_DIRECTORY = Path("data/bronze/prices")


def get_connection() -> psycopg.Connection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from the .env file.")
    return psycopg.connect(database_url)


def find_latest_file(directory: Path, pattern: str) -> Path:
    files = sorted(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern} found in {directory}.")
    return files[-1]


def safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        result = float(value)
        return None if pd.isna(result) else result
    except (TypeError, ValueError):
        return None


def clean_product(product: dict[str, Any]) -> dict[str, Any] | None:
    barcode = str(product.get("code", "")).strip()
    product_name = str(product.get("product_name", "")).strip()
    if not barcode or not product_name or product_name == barcode:
        return None

    nutriments = product.get("nutriments") or {}
    categories = product.get("categories_tags") or []
    category = categories[0] if categories else "unknown"
    modified_timestamp = product.get("last_modified_t")

    if modified_timestamp:
        modified_at = pd.to_datetime(
            modified_timestamp, unit="s", utc=True, errors="coerce"
        )
        modified_at = None if pd.isna(modified_at) else modified_at.to_pydatetime()
    else:
        modified_at = None

    return {
        "barcode": barcode,
        "product_name": product_name[:500],
        "brand": str(product.get("brands", "")).strip()[:300] or None,
        "category": str(category)[:300],
        "ingredients_text": str(product.get("ingredients_text", "")).strip() or None,
        "energy_kcal_100g": safe_float(nutriments.get("energy-kcal_100g")),
        "source_modified_at": modified_at,
    }


def row_to_json_safe(row: pd.Series) -> dict[str, Any]:
    return {
        key: None if pd.isna(value) else value
        for key, value in row.to_dict().items()
    }


def quarantine_record(
    connection: psycopg.Connection,
    run_id: UUID,
    dataset_name: str,
    reason: str,
    raw_record: dict[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO audit.quarantine (
            pipeline_run_id, dataset_name, failure_reason, raw_record
        ) VALUES (%s, %s, %s, %s)
        """,
        (run_id, dataset_name, reason, Jsonb(raw_record)),
    )


def main() -> None:
    run_id = uuid4()
    product_file = find_latest_file(PRODUCT_DIRECTORY, "products_*.json")
    price_file = find_latest_file(PRICE_DIRECTORY, "prices_*.csv")
    raw_products = json.loads(product_file.read_text(encoding="utf-8"))["products"]
    price_frame = pd.read_csv(
        price_file,
        dtype={
            "event_id": "string",
            "barcode": "string",
            "store_id": "string",
            "price": "string",
        },
    )

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO audit.pipeline_runs
                (pipeline_run_id, pipeline_name, status, source_records)
            VALUES (%s, %s, %s, %s)
            """,
            (
                run_id,
                "smart_grocery_daily_pipeline",
                "RUNNING",
                len(raw_products) + len(price_frame),
            ),
        )
        connection.commit()

    valid_product_count = 0
    valid_price_count = 0
    rejected_count = 0

    try:
        with get_connection() as connection:
            for product in raw_products:
                connection.execute(
                    """
                    INSERT INTO bronze.raw_products (source_file, payload)
                    VALUES (%s, %s)
                    """,
                    (product_file.name, Jsonb(product)),
                )
                semantic_result = validate_product_rules(product)
                if (
                    semantic_result.status == "pass"
                    and os.getenv("OLLAMA_SEMANTIC_VALIDATION", "false").lower()
                    in {"1", "true", "yes"}
                ):
                    semantic_result = validate_product_with_ollama(product)

                connection.execute(
                    """
                    INSERT INTO audit.ai_validation_results (
                        pipeline_run_id, barcode, status, confidence,
                        reasons, validator
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        run_id,
                        str(product.get("code", "")).strip() or None,
                        semantic_result.status,
                        semantic_result.confidence,
                        Jsonb(semantic_result.reasons),
                        semantic_result.validator,
                    ),
                )

                cleaned = (
                    clean_product(product)
                    if semantic_result.status == "pass"
                    or semantic_result.confidence < 0.90
                    else None
                )
                if cleaned is None:
                    rejected_count += 1
                    barcode = str(product.get("code", "")).strip()
                    if barcode:
                        connection.execute(
                            "DELETE FROM silver.prices WHERE barcode = %s",
                            (barcode,),
                        )
                        connection.execute(
                            "DELETE FROM silver.products WHERE barcode = %s",
                            (barcode,),
                        )
                    quarantine_record(
                        connection,
                        run_id,
                        "products",
                        "; ".join(semantic_result.reasons)
                        or "Product failed semantic validation",
                        product,
                    )
                    continue

                connection.execute(
                    """
                    INSERT INTO silver.products (
                        barcode, product_name, brand, category,
                        ingredients_text, energy_kcal_100g, source_modified_at
                    ) VALUES (
                        %(barcode)s, %(product_name)s, %(brand)s, %(category)s,
                        %(ingredients_text)s, %(energy_kcal_100g)s,
                        %(source_modified_at)s
                    )
                    ON CONFLICT (barcode) DO UPDATE SET
                        product_name = EXCLUDED.product_name,
                        brand = EXCLUDED.brand,
                        category = EXCLUDED.category,
                        ingredients_text = EXCLUDED.ingredients_text,
                        energy_kcal_100g = EXCLUDED.energy_kcal_100g,
                        source_modified_at = EXCLUDED.source_modified_at,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    cleaned,
                )
                valid_product_count += 1

            valid_barcodes = {
                row[0]
                for row in connection.execute(
                    "SELECT barcode FROM silver.products"
                ).fetchall()
            }
            valid_stores = {
                row[0]
                for row in connection.execute(
                    "SELECT store_id FROM silver.stores"
                ).fetchall()
            }
            seen_events: set[str] = set()

            for _, row in price_frame.iterrows():
                raw_record = row_to_json_safe(row)
                connection.execute(
                    """
                    INSERT INTO bronze.raw_prices (source_file, payload)
                    VALUES (%s, %s)
                    """,
                    (price_file.name, Jsonb(raw_record)),
                )
                failures: list[str] = []
                event_id = str(raw_record.get("event_id") or "").strip()
                barcode = str(raw_record.get("barcode") or "").strip()
                store_id = str(raw_record.get("store_id") or "").strip()
                price = safe_float(raw_record.get("price"))
                event_timestamp = pd.to_datetime(
                    raw_record.get("event_timestamp"), utc=True, errors="coerce"
                )

                if not event_id:
                    failures.append("Missing event ID")
                elif event_id in seen_events:
                    failures.append("Duplicate event ID in source file")
                if barcode not in valid_barcodes:
                    failures.append("Unknown product barcode")
                if store_id not in valid_stores:
                    failures.append("Unknown store")
                if price is None:
                    failures.append("Missing or invalid price")
                elif price <= 0:
                    failures.append("Price must be greater than zero")
                elif price > 500:
                    failures.append("Price exceeds reasonable limit")
                if pd.isna(event_timestamp):
                    failures.append("Invalid event timestamp")
                elif event_timestamp > pd.Timestamp.now(tz="UTC") + pd.Timedelta(minutes=5):
                    failures.append("Timestamp is in the future")

                if failures:
                    rejected_count += 1
                    quarantine_record(
                        connection, run_id, "prices", "; ".join(failures), raw_record
                    )
                    continue

                seen_events.add(event_id)
                promotion = str(raw_record.get("promotion", "")).lower() in {
                    "true",
                    "1",
                    "yes",
                }
                connection.execute(
                    """
                    INSERT INTO silver.prices (
                        event_id, barcode, store_id, price, promotion,
                        stock_status, event_timestamp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        event_id,
                        barcode,
                        store_id,
                        price,
                        promotion,
                        str(raw_record.get("stock_status") or "unknown"),
                        event_timestamp.to_pydatetime(),
                    ),
                )
                valid_price_count += 1
            connection.commit()

        with get_connection() as connection:
            connection.execute(
                """
                UPDATE audit.pipeline_runs
                SET status = 'SUCCESS', valid_records = %s,
                    rejected_records = %s, completed_at = CURRENT_TIMESTAMP
                WHERE pipeline_run_id = %s
                """,
                (
                    valid_product_count + valid_price_count,
                    rejected_count,
                    run_id,
                ),
            )
            connection.commit()

        print("Pipeline completed successfully.")
        print(f"Run ID: {run_id}")
        print(f"Valid products: {valid_product_count}")
        print(f"Valid prices: {valid_price_count}")
        print(f"Rejected records: {rejected_count}")

    except Exception as error:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE audit.pipeline_runs
                SET status = 'FAILED', rejected_records = %s,
                    completed_at = CURRENT_TIMESTAMP, error_message = %s
                WHERE pipeline_run_id = %s
                """,
                (rejected_count, str(error)[:2000], run_id),
            )
            connection.commit()
        raise


if __name__ == "__main__":
    main()

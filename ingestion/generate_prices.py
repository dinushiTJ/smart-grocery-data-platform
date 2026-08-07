#!/usr/bin/env python3
"""Generate fictional supermarket price records with quality anomalies."""

from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PRODUCT_DIRECTORY = Path("data/bronze/products")
OUTPUT_DIRECTORY = Path("data/bronze/prices")

STORES = [
    "hamilton_01",
    "hamilton_02",
    "auckland_01",
    "wellington_01",
    "christchurch_01",
]


def find_latest_product_file() -> Path:
    files = sorted(PRODUCT_DIRECTORY.glob("products_*.json"))
    if not files:
        raise FileNotFoundError(
            "No product file found. Run extract_products.py first."
        )
    return files[-1]


def load_products() -> list[dict]:
    input_path = find_latest_product_file()
    body = json.loads(input_path.read_text(encoding="utf-8"))
    return body["products"]


def generate_price_rows(products: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for product in products:
        barcode = str(product.get("code", "")).strip()
        if not barcode:
            continue

        selected_stores = random.sample(STORES, k=random.randint(2, len(STORES)))
        base_price = random.uniform(1.50, 20.00)
        for store_id in selected_stores:
            row = {
                "event_id": str(uuid4()),
                "barcode": barcode,
                "store_id": store_id,
                "price": round(base_price * random.uniform(0.85, 1.20), 2),
                "promotion": random.random() < 0.20,
                "stock_status": random.choice(
                    ["in_stock", "in_stock", "in_stock", "low_stock"]
                ),
                "event_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # These anomalies exercise validation and quarantine processing.
            problem_chance = random.random()
            if problem_chance < 0.02:
                row["price"] = -1
            elif problem_chance < 0.04:
                row["price"] = ""
            elif problem_chance < 0.06:
                row["store_id"] = "unknown_store"
            elif problem_chance < 0.08:
                row["barcode"] = "unknown_barcode"
            rows.append(row)
    return rows


def save_prices(rows: list[dict]) -> Path:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = OUTPUT_DIRECTORY / f"prices_{timestamp}.csv"
    fieldnames = [
        "event_id",
        "barcode",
        "store_id",
        "price",
        "promotion",
        "stock_status",
        "event_timestamp",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def main() -> None:
    products = load_products()
    rows = generate_price_rows(products)
    output_path = save_prices(rows)
    print(f"Generated {len(rows)} price records.")
    print(f"Saved raw file to {output_path}")


if __name__ == "__main__":
    main()

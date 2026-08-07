#!/usr/bin/env python3
"""Extract a sample of beverage products from Open Food Facts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


API_URL = "https://world.openfoodfacts.org/api/v2/search"
OUTPUT_DIRECTORY = Path("data/bronze/products")

FIELDS = ",".join(
    [
        "code",
        "product_name",
        "brands",
        "categories_tags",
        "countries_tags",
        "ingredients_text",
        "nutriments",
        "last_modified_t",
    ]
)


def extract_products(page_size: int = 100) -> list[dict[str, Any]]:
    """Retrieve a small product sample from Open Food Facts."""
    headers = {
        "User-Agent": (
            "SmartGroceryDataPlatform/1.0 "
            "(portfolio project; contact@example.com)"
        )
    }
    params = {
        "categories_tags_en": "beverages",
        "page": 1,
        "page_size": page_size,
        "fields": FIELDS,
    }

    response = requests.get(API_URL, headers=headers, params=params, timeout=60)
    response.raise_for_status()
    products = response.json().get("products", [])
    valid_products = [
        product for product in products if str(product.get("code", "")).strip()
    ]
    if not valid_products:
        raise RuntimeError("The API returned no usable products.")
    return valid_products


def save_products(products: list[dict[str, Any]]) -> Path:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc)
    output_path = OUTPUT_DIRECTORY / f"products_{fetched_at.strftime('%Y%m%dT%H%M%SZ')}.json"
    output = {
        "fetched_at": fetched_at.isoformat(),
        "record_count": len(products),
        "products": products,
    }
    output_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return output_path


def main() -> None:
    products = extract_products(page_size=100)
    output_path = save_products(products)
    print(f"Extracted {len(products)} products.")
    print(f"Saved raw file to {output_path}")


if __name__ == "__main__":
    main()

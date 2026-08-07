#!/usr/bin/env python3
"""Great Expectations checks for raw product files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd


KNOWN_EXPECTATIONS = (
    "barcode_not_null",
    "product_name_not_null",
    "energy_kcal_100g_in_range",
)


def products_to_frame(path: Path) -> pd.DataFrame:
    body: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    products = body.get("products", [])
    rows = []
    for product in products:
        nutriments = product.get("nutriments") or {}
        rows.append(
            {
                "barcode": product.get("code"),
                "product_name": product.get("product_name"),
                "energy_kcal_100g": nutriments.get("energy-kcal_100g"),
            }
        )
    return pd.DataFrame(rows)


def validate_products(frame: pd.DataFrame) -> dict[str, bool]:
    context = gx.get_context(mode="ephemeral")
    source = context.sources.add_pandas(name="products_source")
    asset = source.add_dataframe_asset(name="products")
    validator = context.get_validator(
        batch_request=asset.build_batch_request(dataframe=frame),
        create_expectation_suite_with_name="products_suite",
    )
    checks = {
        "barcode_not_null": validator.expect_column_values_to_not_be_null(
            "barcode"
        ),
        "product_name_not_null": validator.expect_column_values_to_not_be_null(
            "product_name"
        ),
        "energy_kcal_100g_in_range": validator.expect_column_values_to_be_between(
            "energy_kcal_100g", min_value=0, max_value=1000
        ),
    }
    return {name: result.success for name, result in checks.items()}

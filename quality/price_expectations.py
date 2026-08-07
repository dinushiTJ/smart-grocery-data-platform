#!/usr/bin/env python3
"""Great Expectations checks for raw price files."""

from __future__ import annotations

from pathlib import Path

import great_expectations as gx
import pandas as pd


STORES = {
    "hamilton_01",
    "hamilton_02",
    "auckland_01",
    "wellington_01",
    "christchurch_01",
}


def load_prices(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def validate_prices(frame: pd.DataFrame) -> dict[str, bool]:
    context = gx.get_context(mode="ephemeral")
    source = context.sources.add_pandas(name="prices_source")
    asset = source.add_dataframe_asset(name="prices")
    validator = context.get_validator(
        batch_request=asset.build_batch_request(dataframe=frame),
        create_expectation_suite_with_name="prices_suite",
    )
    checks = {
        "event_id_not_null": validator.expect_column_values_to_not_be_null(
            "event_id"
        ),
        "event_id_unique": validator.expect_column_values_to_be_unique("event_id"),
        "price_in_range": validator.expect_column_values_to_be_between(
            "price", min_value=0, max_value=500, strict_min=True, strict_max=True
        ),
        "store_id_known": validator.expect_column_values_to_be_in_set(
            "store_id", value_set=sorted(STORES)
        ),
        "event_timestamp_not_null": validator.expect_column_values_to_not_be_null(
            "event_timestamp"
        ),
    }
    return {name: result.success for name, result in checks.items()}

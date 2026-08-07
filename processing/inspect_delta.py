#!/usr/bin/env python3
"""Inspect the file-based Delta streaming outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from processing.streaming_prices import create_spark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prices", type=Path, default=Path("data/stream/delta_prices")
    )
    parser.add_argument(
        "--latest", type=Path, default=Path("data/stream/latest_prices")
    )
    args = parser.parse_args()

    spark = create_spark()
    spark.sparkContext.setLogLevel("ERROR")
    prices = spark.read.format("delta").load(str(args.prices))
    latest = spark.read.format("delta").load(str(args.latest))

    print("Streaming prices:")
    prices.show(truncate=False)
    print(f"Streaming rows: {prices.count()}")
    print("Latest prices:")
    latest.show(truncate=False)
    print(f"Latest rows: {latest.count()}")
    spark.stop()


if __name__ == "__main__":
    main()

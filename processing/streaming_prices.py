#!/usr/bin/env python3
"""Process file-based price events with Spark Structured Streaming and Delta Lake."""

from __future__ import annotations

import argparse
from pathlib import Path

from delta import configure_spark_with_delta_pip
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import col, expr, max as spark_max, max_by, when
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


KNOWN_STORES = (
    "hamilton_01",
    "hamilton_02",
    "auckland_01",
    "wellington_01",
    "christchurch_01",
)

EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("barcode", StringType(), False),
        StructField("store_id", StringType(), False),
        StructField("price", DoubleType(), True),
        StructField("currency", StringType(), True),
        StructField("promotion", BooleanType(), True),
        StructField("stock_status", StringType(), True),
        StructField("event_time", TimestampType(), True),
    ]
)


def create_spark() -> SparkSession:
    builder = (
        SparkSession.builder.appName("smart-grocery-streaming-prices")
        .master("local[2]")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
    )
    return configure_spark_with_delta_pip(builder).getOrCreate()


def add_validation_columns(events: DataFrame) -> tuple[DataFrame, DataFrame]:
    valid_store = col("store_id").isin(*KNOWN_STORES)
    valid = (
        events.withColumn(
            "validation_error",
            when(col("event_id").isNull(), "missing event_id")
            .when(col("barcode").isNull(), "missing barcode")
            .when(~valid_store, "unknown store")
            .when(col("price").isNull(), "missing price")
            .when((col("price") <= 0) | (col("price") >= 500), "invalid price")
            .when(col("event_time").isNull(), "missing event_time"),
        )
    )
    invalid = valid.filter(col("validation_error").isNotNull())
    clean = valid.filter(col("validation_error").isNull()).drop("validation_error")
    return clean, invalid


def start_streaming(
    input_directory: Path,
    checkpoint_directory: Path,
    delta_directory: Path,
    quarantine_directory: Path,
    latest_directory: Path,
    once: bool = False,
) -> None:
    spark = create_spark()
    spark.sparkContext.setLogLevel("WARN")
    for directory in (
        checkpoint_directory,
        delta_directory,
        quarantine_directory,
        latest_directory,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    events = (
        spark.readStream.schema(EVENT_SCHEMA)
        .option("maxFilesPerTrigger", 1)
        .json(str(input_directory))
        .withWatermark("event_time", "10 minutes")
        .dropDuplicates(["event_id"])
    )
    valid, invalid = add_validation_columns(events)

    valid_query = (
        valid.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", str(checkpoint_directory / "valid"))
        .option("path", str(delta_directory))
    )
    invalid_query = (
        invalid.writeStream.format("json")
        .outputMode("append")
        .option("checkpointLocation", str(checkpoint_directory / "quarantine"))
        .option("path", str(quarantine_directory))
    )
    latest = (
        valid.groupBy("barcode", "store_id")
        .agg(
            max_by("price", "event_time").alias("latest_price"),
            spark_max("event_time").alias("latest_event_time"),
        )
    )
    latest_query = (
        latest.writeStream.format("delta")
        .outputMode("complete")
        .option("checkpointLocation", str(checkpoint_directory / "latest"))
        .option("path", str(latest_directory))
    )

    queries = [
        valid_query.trigger(availableNow=True if once else None).start(),
        invalid_query.trigger(availableNow=True if once else None).start(),
        latest_query.trigger(availableNow=True if once else None).start(),
    ]
    if once:
        for query in queries:
            query.awaitTermination()
    else:
        spark.streams.awaitAnyTermination()
    spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--input", type=Path, default=Path("data/stream/incoming"))
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("data/stream/checkpoints")
    )
    parser.add_argument(
        "--delta", type=Path, default=Path("data/stream/delta_prices")
    )
    parser.add_argument(
        "--quarantine", type=Path, default=Path("data/stream/quarantine")
    )
    parser.add_argument(
        "--latest", type=Path, default=Path("data/stream/latest_prices")
    )
    args = parser.parse_args()
    start_streaming(
        args.input,
        args.checkpoint,
        args.delta,
        args.quarantine,
        args.latest,
        args.once,
    )


if __name__ == "__main__":
    main()

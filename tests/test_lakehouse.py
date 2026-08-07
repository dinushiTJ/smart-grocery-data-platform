from pathlib import Path

import pytest

from serving.lakehouse import (
    DELTA_PRICES,
    GOLD_MODELS,
    WAREHOUSE_ALIAS,
    attach_lake,
    connect,
    postgres_dsn,
)


def test_postgres_dsn_translates_database_url(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://grocery_user:secret@localhost:5432/grocery"
    )
    dsn = postgres_dsn()

    assert "dbname=grocery" in dsn
    assert "host=localhost" in dsn
    assert "port=5432" in dsn
    assert "user=grocery_user" in dsn
    assert "password=secret" in dsn


def test_postgres_dsn_requires_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError):
        postgres_dsn()


def test_every_gold_model_spans_both_tiers() -> None:
    """A model that reads only one tier belongs in dbt or Spark, not here."""
    for name, query in GOLD_MODELS.items():
        assert "lake_" in query, f"{name} never reads the lake"
        assert f"{WAREHOUSE_ALIAS}." in query, f"{name} never reads the warehouse"


def test_attach_lake_reads_delta_in_place() -> None:
    if not (DELTA_PRICES / "_delta_log").is_dir():
        pytest.skip("no Delta table yet; run processing/streaming_prices.py first")

    connection = connect(output=None)
    attach_lake(connection)

    view_count = connection.execute("SELECT count(*) FROM lake_price_events").fetchone()[0]
    scan_count = connection.execute(
        f"SELECT count(*) FROM delta_scan('{DELTA_PRICES.as_posix()}')"
    ).fetchone()[0]
    connection.close()

    # Equal counts prove the view is the Delta table itself, not a copy of it.
    assert view_count == scan_count
    assert view_count > 0


def test_lake_views_expose_the_streaming_schema() -> None:
    if not (DELTA_PRICES / "_delta_log").is_dir():
        pytest.skip("no Delta table yet; run processing/streaming_prices.py first")

    connection = connect(output=None)
    attach_lake(connection)
    columns = {
        row[0]
        for row in connection.execute("DESCRIBE lake_price_events").fetchall()
    }
    connection.close()

    assert {"event_id", "barcode", "store_id", "price", "event_time"} <= columns

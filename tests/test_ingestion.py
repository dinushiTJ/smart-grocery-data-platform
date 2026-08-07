import random
import uuid

from ingestion.generate_prices import generate_price_rows
from ingestion.generate_stream_events import generate_events


PRODUCT = {"code": "123", "product": {"categories_tags": ["en:snacks"]}}


def test_generate_prices_has_valid_shape():
    random.seed(7)
    rows = generate_price_rows([PRODUCT])

    assert 2 <= len(rows) <= 5
    assert all(uuid.UUID(row["event_id"]) for row in rows)
    assert {row["store_id"] for row in rows}.issubset(
        {
            "hamilton_01",
            "hamilton_02",
            "auckland_01",
            "wellington_01",
            "christchurch_01",
            "unknown_store",
        }
    )


def test_generate_events_has_unique_ids():
    events = generate_events([PRODUCT], events_per_product=3, seed=7)

    assert len(events) == 3
    assert len({event["event_id"] for event in events}) == 3
    assert all(event["barcode"] == "123" and uuid.UUID(event["event_id"]) for event in events)

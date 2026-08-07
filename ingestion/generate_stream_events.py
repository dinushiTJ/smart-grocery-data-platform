#!/usr/bin/env python3
"""Generate streaming-style price update events as newline-delimited JSON."""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def generate_events(
    products: list[dict], events_per_product: int = 10, seed: int = 42
) -> list[dict]:
    rng = random.Random(seed)
    start = datetime.now(timezone.utc).replace(microsecond=0)
    events = []
    stores = (
        "hamilton_01",
        "hamilton_02",
        "auckland_01",
        "wellington_01",
        "christchurch_01",
    )
    for product_record in products:
        product = product_record.get("product", product_record)
        barcode = str(product_record.get("code") or product.get("code") or "")
        if not barcode:
            continue
        for event_number in range(events_per_product):
            events.append(
                {
                    "event_id": str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"{barcode}:{event_number}:{seed}",
                        )
                    ),
                    "barcode": barcode,
                    "store_id": rng.choice(stores),
                    "price": round(rng.uniform(1.5, 15.0), 2),
                    "currency": "EUR",
                    "promotion": False,
                    "stock_status": "in_stock",
                    "event_time": (start + timedelta(seconds=event_number)).isoformat(),
                }
            )
    return events


def write_stream_events(
    products: list[dict],
    output_directory: Path,
    interval_seconds: float = 2.0,
    max_events: int | None = None,
    seed: int = 42,
) -> int:
    """Write one JSON event file at a time for file-based streaming."""
    rng = random.Random(seed)
    output_directory.mkdir(parents=True, exist_ok=True)
    valid_products = [
        product
        for product in products
        if str(product.get("code", "")).strip()
    ]
    if not valid_products:
        raise ValueError("No products with barcodes were provided")

    event_number = 0
    try:
        while max_events is None or event_number < max_events:
            product = rng.choice(valid_products)
            barcode = str(product["code"]).strip()
            event = {
                "event_id": str(uuid.uuid4()),
                "barcode": barcode,
                "store_id": rng.choice(
                    (
                        "hamilton_01",
                        "hamilton_02",
                        "auckland_01",
                        "wellington_01",
                        "christchurch_01",
                    )
                ),
                "price": round(rng.uniform(1.5, 15.0), 2),
                "currency": "EUR",
                "promotion": False,
                "stock_status": "in_stock",
                "event_time": datetime.now(timezone.utc).isoformat(),
            }
            event_number += 1
            output_path = output_directory / f"price_event_{event_number:04d}.json"
            output_path.write_text(
                json.dumps(event) + "\n", encoding="utf-8"
            )
            print(f"Wrote {output_path}", flush=True)
            if max_events is None or event_number < max_events:
                time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("Streaming event generation stopped.")
    return event_number


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/bronze/price_events.jsonl"))
    parser.add_argument("--events-per-product", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--stream", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--max-events", type=int)
    parser.add_argument(
        "--stream-output",
        type=Path,
        default=Path("data/stream/incoming"),
    )
    args = parser.parse_args()
    if args.events_per_product < 1:
        parser.error("--events-per-product must be positive")
    if args.interval < 0:
        parser.error("--interval cannot be negative")
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "products" in payload:
        payload = payload["products"]
    products = [payload] if isinstance(payload, dict) else payload
    if args.stream:
        count = write_stream_events(
            products,
            args.stream_output,
            args.interval,
            args.max_events,
            args.seed,
        )
        print(f"Wrote {count} streaming events.")
        return

    events = generate_events(products, args.events_per_product, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )
    print(f"Wrote {len(events)} events to {args.output}")


if __name__ == "__main__":
    main()

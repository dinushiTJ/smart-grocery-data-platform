#!/usr/bin/env python3
"""Rewrite the streaming and cross-tier figures in site/index.html from DuckDB.

``refresh_figures.py`` owns everything the warehouse knows. Section 07 and the footer describe
the *other* tier, which lives in the Delta tables and in ``data/gold/lakehouse.duckdb``, so it
was left as hand-typed text. That turned out to be a trap: re-running the batch pipeline moves
the batch side of every cross-tier comparison, and the page silently kept quoting the old
numbers. One re-run left "13 of the 94 land within a dollar" on a page whose data said 19.

So these figures are generated too. Same contract as the warehouse refresher: each value lives
in an element carrying ``data-fig="..."``, and ``--check`` fails when the page has drifted.

    python3 site/refresh_stream_figures.py            # rewrite the page
    python3 site/refresh_stream_figures.py --check    # exit 1 if the page has drifted

Run it after ``python3 -m serving.lakehouse``, which is what rebuilds the DuckDB file.

Two figures appear twice on the page (the product count and the both-routes count), which the
substitution cannot express, so the second occurrence carries a ``.b`` suffix and is fed the
same value.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

# reuse the page contract rather than restating it: same apply(), same escaping
from refresh_figures import PAGE, apply, esc

REPO = Path(__file__).resolve().parent.parent
LAKEHOUSE = REPO / "data" / "gold" / "lakehouse.duckdb"


def disagreement_table(rows) -> str:
    """The five widest gaps, as table rows. Negative numbers use a real minus sign."""
    out = []
    for name, stream_price, batch_price, difference in rows:
        gap = f"&minus;{abs(difference):.2f}" if difference < 0 else f"{difference:.2f}"
        out.append(
            f'<tr><td class="a-l">{esc(name)}</td>'
            f'<td class="a-r">{stream_price:.2f}</td>'
            f'<td class="a-r">{batch_price:.2f}</td>'
            f'<td class="a-r">{gap}</td></tr>'
        )
    return "".join(out)


def fetch() -> dict[str, str]:
    """Read every cross-tier figure the page displays, in one pass over DuckDB."""
    if not LAKEHOUSE.exists():
        raise SystemExit(
            f"{LAKEHOUSE} is missing. Build it with: python3 -m serving.lakehouse"
        )

    connection = duckdb.connect(str(LAKEHOUSE), read_only=True)
    try:
        def scalar(sql: str):
            return connection.execute(sql).fetchone()[0]

        events = scalar("SELECT count(*) FROM lake_price_events")
        latest_rows = scalar("SELECT count(*) FROM lake_latest_price")
        products = scalar("SELECT count(*) FROM gold_streamed_price_by_product")
        stores = scalar("SELECT count(*) FROM gold_streamed_events_by_store")
        both = scalar("SELECT count(*) FROM gold_stream_versus_batch")
        within = scalar(
            "SELECT count(*) FROM gold_stream_versus_batch WHERE abs(difference) <= 1")
        cheaper = scalar(
            "SELECT count(*) FROM gold_stream_versus_batch WHERE difference < 0")
        median_gap = scalar(
            "SELECT round(median(abs(difference)), 2) FROM gold_stream_versus_batch")
        avg_batch = scalar(
            "SELECT round(avg(batch_price), 2) FROM gold_stream_versus_batch")
        avg_stream = scalar(
            "SELECT round(avg(stream_price), 2) FROM gold_stream_versus_batch")
        widest = connection.execute(
            """SELECT product_name, stream_price, batch_price, difference
               FROM gold_stream_versus_batch ORDER BY difference LIMIT 5"""
        ).fetchall()
    finally:
        connection.close()

    return {
        "stream.events": str(events),
        "stream.latest_rows": str(latest_rows),
        "stream.products": str(products),
        "stream.products.b": str(products),
        "stream.stores": str(stores),
        "stream.both_routes": str(both),
        "stream.both_routes.b": str(both),
        "stream.within_dollar": str(within),
        "stream.cheaper": str(cheaper),
        "stream.median_gap": f"{median_gap:.2f}",
        "stream.avg_batch": f"{avg_batch:.2f}",
        "stream.avg_stream": f"{avg_stream:.2f}",
        "stream.disagreement": disagreement_table(widest),
        "footer.stream": (
            "Streaming and cross-tier figures read from the Delta tables and "
            "<code>data/gold/lakehouse.duckdb</code> in the same session &middot; "
            f"{events} streamed price events &middot; "
            f"{both} products present in both routes."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report drift and exit 1 without writing")
    args = parser.parse_args()

    html = PAGE.read_text()
    updated, changed = apply(html, fetch())

    if args.check:
        if changed:
            print(f"{len(changed)} stream figure(s) stale: {', '.join(sorted(changed))}")
            sys.exit(1)
        print("every stream figure matches the lakehouse")
        return

    if changed:
        PAGE.write_text(updated)
        print(f"refreshed {len(changed)} stream figure(s): {', '.join(sorted(changed))}")
    else:
        print("nothing to do, every stream figure already matches the lakehouse")


if __name__ == "__main__":
    main()

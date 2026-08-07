#!/usr/bin/env python3
"""Rewrite the figures in site/index.html from the warehouse.

Every number on the page used to be hand-copied from a one-off snapshot, so it went
stale the next time Airflow ran the pipeline. Each figure now carries a
``data-fig="..."`` attribute; this script reads the current values out of PostgreSQL
and substitutes them in place.

    python3 site/refresh_figures.py            # rewrite the page
    python3 site/refresh_figures.py --check    # exit 1 if the page has drifted

The streaming figures in section 07 come from the Delta tables rather than the
warehouse and are left alone; regenerate those with ``python3 -m serving.lakehouse``.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PAGE = Path(__file__).with_name("index.html")
REPO = Path(__file__).resolve().parent.parent


def fetch() -> dict[str, str]:
    """Read every figure the page displays, in one pass over the warehouse."""
    load_dotenv(REPO / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing from the .env file.")

    with psycopg.connect(url) as connection, connection.cursor() as cursor:
        def scalar(sql: str):
            cursor.execute(sql)
            return cursor.fetchone()[0]

        raw_products = scalar("SELECT count(*) FROM bronze.raw_products")
        raw_prices = scalar("SELECT count(*) FROM bronze.raw_prices")
        products = scalar("SELECT count(*) FROM silver.products")
        prices = scalar("SELECT count(*) FROM silver.prices")
        stores = scalar("SELECT count(*) FROM silver.stores")
        runs = scalar("SELECT count(*) FROM audit.pipeline_runs")
        quarantined = scalar("SELECT count(*) FROM audit.quarantine")

        # the hero describes the most recent finished run, not the totals
        cursor.execute(
            """SELECT source_records, valid_records, rejected_records, started_at
               FROM audit.pipeline_runs
               WHERE status = 'SUCCESS'
               ORDER BY started_at DESC LIMIT 1"""
        )
        source, valid, rejected, started = cursor.fetchone()

        cursor.execute(
            """SELECT failure_reason, count(*) FROM audit.quarantine
               GROUP BY 1 ORDER BY 2 DESC, 1"""
        )
        reasons = cursor.fetchall()

        cursor.execute(
            """SELECT dataset_name, count(*) FROM audit.quarantine
               GROUP BY 1 ORDER BY 2 DESC"""
        )
        datasets = cursor.fetchall()

        cursor.execute(
            """SELECT s.store_name, s.city, round(avg(p.price)::numeric, 2), count(*)
               FROM silver.prices p JOIN silver.stores s USING (store_id)
               GROUP BY 1, 2 ORDER BY 3 DESC"""
        )
        store_rows = cursor.fetchall()

        cursor.execute(
            """SELECT started_at, valid_records, rejected_records
               FROM audit.pipeline_runs ORDER BY started_at"""
        )
        run_rows = cursor.fetchall()

        # ten equal price bands, so the histogram matches whatever silver holds now
        cursor.execute(
            """WITH bounds AS (SELECT min(price) lo, max(price) hi FROM silver.prices),
                    banded AS (SELECT width_bucket(price, lo, hi, 10) AS band,
                                      lo, hi FROM silver.prices, bounds)
               SELECT band, min(lo + (band - 1) * (hi - lo) / 10) AS floor, count(*)
               FROM banded GROUP BY band ORDER BY band"""
        )
        band_rows = cursor.fetchall()

    pct = round(rejected / source * 100, 1) if source else 0.0
    figures = {
        "run.source": str(source),
        "run.valid": str(valid),
        "run.rejected": str(rejected),
        "run.reject_pct": f"{pct:.1f}",
        "bronze.raw_products": f"{raw_products:,} rows",
        "bronze.raw_prices": f"{raw_prices:,} rows",
        "bronze.total": f"{raw_products + raw_prices:,} rows",
        "silver.products": f"{products:,} rows",
        "silver.prices": f"{prices:,} rows",
        "silver.stores": f"{stores:,} rows",
        "silver.total": f"{products + prices + stores:,} rows",
        "audit.runs": f"{runs} runs",
        "runs.count": str(runs),
        "audit.quarantine": f"{quarantined:,} rows",
        "audit.summary": f"{quarantined:,} quarantined · {runs} runs",
        "quarantine.reasons": bars(top_with_other(reasons, 7)),
        "quarantine.datasets": bars([(d.title(), n) for d, n in datasets]),
        "stores.table": store_table(store_rows),
        "quarantine.total": str(quarantined),
        "silver.prices.count": f"{prices:,}",
        "runs.timeline": run_timeline(run_rows),
        "hero.snapshot": (
            f"Every number here was read from the warehouse on "
            f"{started:%d %B %Y} at {started:%H:%M} UTC. It is a snapshot, not a live feed."
        ),
        "price.histogram": histogram(band_rows),
        "footer.snapshot": (
            f"Warehouse snapshot taken {started:%d %B %Y}, {started:%H:%M} UTC · "
            f"{raw_products:,} raw product rows · {raw_prices:,} raw price rows · "
            f"{quarantined:,} quarantined records across {runs} runs. Airflow advances the "
            f"warehouse daily, so these describe that run rather than this moment."
        ),
    }
    return figures


def top_with_other(rows, keep: int):
    """Keep the largest reasons, fold the tail into one Other bucket."""
    head, tail = rows[:keep], rows[keep:]
    if tail:
        head = head + [("Other", sum(n for _, n in tail))]
    return sorted(head, key=lambda r: -r[1])


def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def bars(rows) -> str:
    top = max((n for _, n in rows), default=1) or 1
    out = []
    for label, count in rows:
        width = round(count / top * 100, 1)
        out.append(
            f'<li class="bar" tabindex="0" data-tip="{esc(label)}: {count}">'
            f'<span class="bar-label">{esc(label)}</span>'
            f'<span class="bar-track"><span class="bar-fill" data-w="{width}"></span></span>'
            f'<span class="bar-value">{count}</span></li>'
        )
    return "".join(out)


def columns(items) -> str:
    """Stacked column chart: each item is (tick, tooltip, [(segment class, height)]).

    A column whose segments are all zero is marked ``data-empty`` so the CSS can
    hatch it; without the attribute an empty run renders as a blank gap and the
    caption's promise of a hatched column is a lie.
    """
    out = []
    for tick, tip, segments in items:
        stack = "".join(
            f'<span class="seg {cls}" data-h="{h}"></span>' for cls, h in segments
        )
        empty = ' data-empty="true"' if not any(h for _, h in segments) else ""
        out.append(
            f'<li class="col"{empty} tabindex="0" data-tip="{esc(tip)}">'
            f'<span class="col-stack">{stack}</span>'
            f'<span class="col-tick">{esc(tick)}</span></li>'
        )
    return "".join(out)


def run_timeline(rows) -> str:
    top = max((v + r for _, v, r in rows), default=1) or 1
    items = []
    for started, valid, rejected in rows:
        total = valid + rejected
        tip = (f"{started:%d %b %H:%M} · {valid} loaded · {rejected} quarantined"
               if total else f"{started:%d %b %H:%M} · no records")
        bad = round(rejected / top * 100, 1)
        good = round(valid / top * 100, 1)
        items.append((f"{started:%H:%M}", tip,
                      [("seg-b", bad), ("seg-a", good)]))
    return columns(items)


def histogram(rows) -> str:
    top = max((n for _, _, n in rows), default=1) or 1
    items = []
    for _, floor, count in rows:
        floor = float(floor)
        items.append((f"{floor:.1f}", f"{floor:.1f}+ · {count} price records",
                      [("seg-a", round(count / top * 100, 1))]))
    return columns(items)


def store_table(rows) -> str:
    out = []
    for name, city, average, count in rows:
        out.append(
            f'<tr><td class="a-l">{esc(name)} ({esc(city)})</td>'
            f'<td class="a-r">{average}</td><td class="a-r">{count}</td></tr>'
        )
    return "".join(out)


# the hero counters are animated: the JS counts up to data-count and overwrites the
# body, so for these the attribute is the thing that has to change
COUNTERS = {"run.source", "run.valid", "run.rejected", "run.reject_pct"}


def apply(html: str, figures: dict[str, str]) -> tuple[str, list[str]]:
    """Substitute each figure into the element that carries its data-fig attribute."""
    changed: list[str] = []
    for name, value in figures.items():
        if name in COUNTERS:
            pattern = re.compile(
                r'(data-fig="' + re.escape(name) + r'"\s+data-count=")([^"]*)(")')
            match = pattern.search(html)
            if not match:
                raise SystemExit(f'no counter carries data-fig="{name}"')
            if match.group(2) != value:
                changed.append(name)
                html = html[:match.start()] + match.group(1) + value + match.group(3) + html[match.end():]
            continue
        pattern = re.compile(
            r'(<(?P<tag>\w+)[^>]*data-fig="' + re.escape(name) + r'"[^>]*>)(?P<body>.*?)(</(?P=tag)>)',
            re.S,
        )
        match = pattern.search(html)
        if not match:
            raise SystemExit(f"no element carries data-fig=\"{name}\"")
        if match.group("body").strip() != value.strip():
            changed.append(name)
            html = html[:match.start()] + match.group(1) + value + match.group(4) + html[match.end():]
    return html, changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report drift and exit 1 without writing")
    args = parser.parse_args()

    html = PAGE.read_text()
    updated, changed = apply(html, fetch())

    if args.check:
        if changed:
            print(f"{len(changed)} figure(s) stale: {', '.join(sorted(changed))}")
            sys.exit(1)
        print("every figure matches the warehouse")
        return

    if changed:
        PAGE.write_text(updated)
        print(f"refreshed {len(changed)} figure(s): {', '.join(sorted(changed))}")
    else:
        print("nothing to do, every figure already matches the warehouse")


if __name__ == "__main__":
    main()

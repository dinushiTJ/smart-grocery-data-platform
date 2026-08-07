# Interview notes

Answers to the questions this project tends to attract. Every number and file reference here
was checked against the running system, not remembered. Where the honest answer is a weakness,
it is written as a weakness.

---

## What is it, in one breath?

A local data platform that takes real product data from Open Food Facts, generates supermarket
prices for it, and pushes both through a validated medallion warehouse into dbt models and
Metabase dashboards. There is a second, separate path where the same price events are streamed
through Spark into Delta tables, and a DuckDB layer that is the only thing able to query both
at once.

The point of the project is not the grocery data. It is that **every record can be accounted
for**: what arrived, what was rejected, why, and by which run.

## Why build this at all?

I wanted a portfolio project where the interesting part was data quality and provenance rather
than volume. Anyone can move rows. The harder questions are the ones a real team asks on a bad
morning: did last night's load work, what did it drop, can I see the record that caused it, and
can I prove the number on the dashboard came from somewhere.

So the design constraint I set was that the platform must never silently lose a record. Raw
data is written to `bronze` **before** validation, rejects go to `audit.quarantine` with the
reason attached, and every run opens and closes a row in `audit.pipeline_runs`.

## Why the medallion layout in a single Postgres database instead of three systems?

Because the layering is a modelling decision, not an infrastructure one. Bronze, silver and
gold are three different promises about how much you can trust a row, and you can make those
promises with three schemas in one database just as well as with three products.

Running it in one Postgres instance meant the whole thing starts with `docker compose up -d`
on a laptop, which matters for a project people are meant to be able to clone and run. The
schema boundaries are still real: `silver.prices` has a primary key on `event_id` and foreign
keys to both `silver.products` and `silver.stores`, so a price for a product that does not
exist is rejected by the database, not just by my Python.

**The trade-off:** this is not how I would build it at scale. There is no separation of compute
from storage, no independent scaling of the layers, and gold is a dbt view rather than a
materialised table. For a laptop-sized portfolio project that is the right call. For anything
real it would move to a warehouse where the layers can scale apart.

## Why generate the prices instead of scraping real ones?

Two reasons, one principled and one practical.

The principled one is that scraping retailer prices without permission is not something I want
in a public portfolio. Open Food Facts is open data and is used as intended. The prices are
clearly labelled as fictional everywhere they appear.

The practical one is that **generated data lets me inject faults deliberately**, which is the
whole point. `ingestion/generate_prices.py` gives every row an 8% chance of being broken, in
four equal 2% bands: a negative price, an empty price, an unknown store, and an unknown
barcode. That guarantees the quarantine path is exercised on every single run rather than
sitting untested until real bad data shows up.

If the rejection rate on the dashboard ever drops to zero, something has broken in the
validator, and I would notice.

## Why is the rejection rate so high? Is that not a failure?

It is the feature. The generator injects roughly 8% faults on purpose, and the observed
rejection rate tracks that. A run that rejects nothing would mean the checks stopped working.

The number to watch is not "how many were rejected" but "does every rejection have a reason
recorded, and does the reason mix match the faults I injected". Section 05 of the site charts
exactly that, split by reason and by dataset.

## Talk me through the validation. Why is there an LLM in it?

There are three layers and they are deliberately not interchangeable.

1. **Deterministic rules** in `quality/semantic_validation.py` run first and are authoritative.
   Required identifiers, meaningful product names, numeric nutrition values, positive prices,
   known stores, valid timestamps.
2. **An optional local LLM** (Ollama with Qwen) can add judgement on top, and only on top.
   `validate_product_with_ollama` short-circuits to the rule result on reject, so the model can
   never rescue a record the rules already killed. It is off by default.
3. **dbt tests** assert the shape of the warehouse output.

The reason the model is boxed in like that is that I did not want a non-deterministic component
making irreversible decisions about data. It can flag, it cannot overrule.

### What does `confidence < 0.90` actually do? It looks like a bug.

It is the part I would expect to be challenged on, and it reads backwards on first look
([`processing/run_pipeline.py:177`](../processing/run_pipeline.py)):

```python
cleaned = (
    clean_product(product)
    if semantic_result.status == "pass" or semantic_result.confidence < 0.90
    else None
)
```

A product is cleaned and loaded if it passed **or** if the validator rejected it without being
confident. In other words, a low-confidence reject is not trusted enough to throw data away.
Only a confident reject actually drops the record.

That is a deliberate hedge against the LLM validator, and I would defend it: the cost of
wrongly dropping a good record is higher here than the cost of admitting a doubtful one,
because the doubtful one is still visible and still auditable downstream. The verdict is
written to `audit.ai_validation_results` either way, so nothing is hidden.

**What I would change:** the threshold is a magic number sitting inline in the middle of the
loop. It should be a named constant with the reasoning next to it, because right now it looks
like an inverted comparison to anyone reading quickly.

## What happens to prices belonging to a product that gets rejected?

They are deleted retroactively. When a product fails validation, the pipeline deletes from
`silver.prices` first and then `silver.products`, in that order because of the foreign key, and
then quarantines the product.

This is why the top rejection reason is usually "unknown product barcode": a rejected product
takes its prices down with it, and those prices then have nothing to point at. The two numbers
are related, and it took some staring at the quarantine table to see that.

## Why file-based streaming? Why is there no Kafka?

Spark Structured Streaming reads a directory as a source, and for demonstrating the streaming
concepts that is enough. `processing/streaming_prices.py` runs three queries off one
`readStream`: valid rows append to Delta, invalid rows append to a quarantine folder, and a
`groupBy(barcode, store_id)` aggregate maintains a latest-price table in complete mode. It has
an explicit schema, a ten-minute watermark, and `dropDuplicates` on `event_id`.

Every one of those ideas transfers to Kafka unchanged. What Kafka would add is durability,
replay, partitioning and consumer groups, none of which I can meaningfully demonstrate on one
laptop, against the cost of another service to run before anyone can see the project work.

I would rather ship a small honest thing and say what it does not cover than run a broker to
look serious.

## Why two tiers at all, and what is `gold_stream_versus_batch` for?

Because the interesting question is the one neither tier can answer alone.

The batch tier lands prices in Postgres. The streaming tier lands them in Delta files. Neither
knows the other exists. `serving/lakehouse.py` opens DuckDB, `delta_scan`s the Delta directories
as views, attaches Postgres **read only**, and materialises gold models that require both
sides.

`gold_stream_versus_batch` exists specifically to surface the disagreement. Right now the two
generators draw from different ranges, so the streaming average sits well below the batch one
and the model reports a large gap. That gap is invented, but the mechanism is not: this is
exactly the query you would write to catch a real reconciliation failure between a stream and
a nightly load, and section 07 of the site shows the five widest offenders.

Two of those five are the same drink under two barcodes with different spellings, which is a
genuine property of open product data and the reason the platform keys on barcode rather than
name.

## How do you know the numbers on your documentation site are true?

Because they are not typed. Every figure on the page carries a `data-fig` attribute and is
written by a script that reads the source of truth:

- `site/refresh_figures.py` pulls from Postgres.
- `site/refresh_stream_figures.py` pulls from `data/gold/lakehouse.duckdb`.

Both take `--check`, which exits non-zero if the page has drifted, so staleness is a build
failure rather than something a reader has to catch.

That second script exists because I got caught. The streaming figures in section 07 were
hardcoded prose, and a batch re-run silently moved the batch side of every cross-tier
comparison. The page went on claiming "13 of the 94 land within a dollar" when the data said
19. The lesson I actually took from it is that a number in prose is a number that will
eventually be wrong, so the fix was to put it under the same generator contract as the rest.

## What is wrong with this project?

Taken straight from the platform's own limitations section, all verified:

- **Great Expectations is defined but wired to nothing.** The suites in `quality/` are correct
  and nothing imports them. It is a gap, not a layer, and the site says so rather than listing
  it as a feature.
- **The rules are implemented twice.** The streaming tier re-implements validation as a Spark
  expression instead of importing `quality/semantic_validation.py`, and the store list is
  hardcoded in five files. Nothing stops the copies drifting and no test would catch it.
- **The streaming quarantine has never caught anything.** Its rules work, but the stream
  generator injects no faults the way the batch generator does, so the folder holds over 400
  empty files and not one rejected record.
- **Prices have no history.** The generator stamps every row with the clock at the moment it
  runs, so a whole run lands inside the same second. There is no trend to plot, which makes the
  time dimension decorative.
- **One product category.** The extract is filtered to beverages, so any chart grouped by
  category is a single bar. One dashboard card was removed for this reason.
- **Store differences are not real.** All five stores draw from the same distribution, so
  ranking them is meaningless by construction.
- **Airflow ships local-only secrets.** The pipeline's own `DATABASE_URL` is required from the
  environment and the stack refuses to start without it, but Airflow's own metadata database
  and API signing key still fall back to defaults in its compose file.

## What would you do next, and why in that order?

1. **Wire up Great Expectations**, because it is the only thing on that list that is a missing
   layer rather than a known simplification.
2. **Collapse the duplicated validation** into one shared module used by both tiers, and add a
   test that fails when the store lists diverge. Right now the drift is silent, which is worse
   than the duplication.
3. **Spread `event_timestamp` across a date range**, which turns the time dimension from
   decorative into real and makes trend analysis possible.
4. **Inject faults into the stream generator** so the streaming quarantine is exercised the way
   the batch one is.
5. Only then Kafka, and cloud deployment through OpenTofu.

The ordering is deliberate: everything above the line makes existing claims more true, and
everything below it adds surface area. I would rather finish the honesty work first.

## What did you find hardest?

Keeping the documentation true. The pipeline itself is not conceptually difficult. Making a
page that describes a moving system and does not quietly become a lie turned out to be the
part that needed real engineering, and it is why the figure refreshers, their `--check` modes,
and the CI guards exist at all.

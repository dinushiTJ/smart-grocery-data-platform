# Screenshots

Captures from the local stack, at full resolution. The root `README.md` links these directly.

`site/index.html` does **not**. The page may never reference anything outside `site/` — a
browser opening it over `file://` can refuse to read a parent directory, which silently broke
every image on the page. `site/build_assets.py` derives downscaled copies into `site/assets/`
and the page points at those. Re-run it after re-exporting anything here:

```bash
python3 site/build_assets.py            # rebuild any stale or missing asset
python3 site/build_assets.py --check    # exit 1 if an asset is out of date
```

The filenames are load-bearing in both places — rename one here and you must rebuild the
assets and fix the README link.

| File | What it shows |
| --- | --- |
| `airflow-dag-run.png` | `smart_grocery_pipeline`, run `manual__2026-08-06T02:34:43`, all three tasks Success |
| `spark-delta-streaming.png` | Spark 3.5.9 UI, `smart-grocery-streaming-prices`, three active queries |
| `dbt-tests.png` | `dbt test` — 4 of 4 `not_null` tests passing on `daily_price_summary` |
| `dbt-lineage.png` | dbt lineage: `silver.prices` + `silver.products` → `daily_price_summary` |
| `metabase-data-quality.png` | Metabase data-quality tab, 06 Aug 02:34 run (450 / 396 / 54) |
| `metabase-pricing-1.png` | Metabase pricing tab, upper half, same run |
| `metabase-pricing-2.png` | Metabase pricing tab, lower half, same run |

The two Metabase PDFs are the original exports. Regenerate the PNGs from them with:

```bash
cd docs/screenshots
gs -dNOPAUSE -dBATCH -sDEVICE=png16m -r150 -dTextAlphaBits=4 -dGraphicsAlphaBits=4 \
   -sOutputFile=metabase-data-quality.png "Metabase - Data Quality.pdf"
gs -dNOPAUSE -dBATCH -sDEVICE=png16m -r150 -dTextAlphaBits=4 -dGraphicsAlphaBits=4 \
   -sOutputFile=metabase-pricing-%d.png "Metabase - Smart Grocery Pricing.pdf"
```

The Metabase exports are dated: they show the `2026-08-06T02:34` run, while the site and the
warehouse have since moved on to `2026-08-07T00:15`. Re-export both tabs from
`http://localhost:3001` to bring them level, and update the run labels in the section 08
captions and in the root `README.md` when you do.

## Still to capture

- `sql-performance.png` — the `EXPLAIN ANALYZE` before/after. Recorded as text in
  `docs/query-performance.md` in the meantime.
- `github-actions.png` — a passing CI run.

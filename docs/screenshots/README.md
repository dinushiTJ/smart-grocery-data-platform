# Screenshots

Captures from the local stack, at full resolution. The root `README.md` links these directly.

`site/index.html` does **not**. The page may never reference anything outside `site/`, because a
browser opening it over `file://` can refuse to read a parent directory, which silently broke
every image on the page. `site/build_assets.py` derives downscaled copies into `site/assets/`
and the page points at those. Re-run it after re-exporting anything here:

```bash
python3 site/build_assets.py            # rebuild any stale or missing asset
python3 site/build_standalone.py        # then rebuild the one-file copy that embeds them
```

Both, in that order. `site/walkthrough.html` inlines these images, so re-exporting a screenshot
without rebuilding it leaves the double-clickable copy showing the old capture. `--check` on
either script exits 1 when its output is out of date.

The filenames are load-bearing in both places. Rename one here and you must rebuild the
assets and fix the README link.

| File | What it shows |
| --- | --- |
| `airflow-dag-run.png` | `smart_grocery_pipeline`, run `manual__2026-08-06T02:34:43`, all three tasks Success |
| `spark-delta-streaming.png` | Spark 3.5.9 UI, `smart-grocery-streaming-prices`, three active queries |
| `dbt-tests.png` | `dbt test`, 4 of 4 `not_null` tests passing on `daily_price_summary` |
| `dbt-lineage.png` | dbt lineage: `silver.prices` + `silver.products` → `daily_price_summary` |
| `metabase-data-quality.png` | Metabase data-quality tab, light, 07 Aug 03:17 run (446 / 406 / 40) |
| `metabase-pricing-1.png` | Metabase pricing tab, upper half, light, same run (1,517 prices, avg EUR 10.87) |
| `metabase-pricing-2.png` | Metabase pricing tab, lower half, light, same run |
| `metabase-*-dark.png` | The same three tabs exported in Metabase's dark theme |

The three `metabase-*.png` files are exported straight from Metabase at
`http://localhost:3001`. Export both dashboard tabs and drop the PNGs in here.

Each Metabase tab is exported twice, light and dark, because section 08 swaps them to follow
the page theme. The `-dark` suffix is what the page looks for, so keep it.

The Metabase exports currently show the `2026-08-07T03:17` run, the same one the site
describes. They will fall behind the next time Airflow runs, because Metabase queries the
warehouse live while these are stills. After re-exporting, update the run labels in the
section 08 captions of `site/index.html` and in the root `README.md`, then rebuild.

## Still to capture

- `sql-performance.png`: the `EXPLAIN ANALYZE` before and after. Recorded as text in
  `docs/query-performance.md` in the meantime.
- `github-actions.png`: a passing CI run.

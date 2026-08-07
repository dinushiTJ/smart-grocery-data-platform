# Query Performance

The comparison uses barcode `16256866` on `silver.prices`, which contained 317 rows during the test.

## Before Indexes

```text
Sort (cost=9.02..9.03 rows=5 width=40) (actual time=0.054..0.055 rows=5 loops=1)
  Sort Key: event_timestamp DESC
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=8
  ->  Seq Scan on prices (cost=0.00..8.96 rows=5 width=40) (actual time=0.013..0.027 rows=5 loops=1)
        Filter: (barcode = '16256866'::text)
        Rows Removed by Filter: 312
        Buffers: shared hit=5
Planning Time: 0.314 ms
Execution Time: 0.085 ms
```

## Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_prices_barcode_timestamp
ON silver.prices (barcode, event_timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_prices_store_timestamp
ON silver.prices (store_id, event_timestamp DESC);
```

## After Indexes

```text
Sort (cost=9.02..9.03 rows=5 width=40) (actual time=0.038..0.038 rows=5 loops=1)
  Sort Key: event_timestamp DESC
  Sort Method: quicksort  Memory: 25kB
  Buffers: shared hit=8
  ->  Seq Scan on prices (cost=0.00..8.96 rows=5 width=40) (actual time=0.013..0.025 rows=5 loops=1)
        Filter: (barcode = '16256866'::text)
        Rows Removed by Filter: 312
        Buffers: shared hit=5
Planning Time: 0.400 ms
Execution Time: 0.062 ms
```

## Conclusion

PostgreSQL retained a sequential scan because the table is small and scanning 317 rows is cheaper than using an index. The measured execution time decreased from `0.085 ms` to `0.062 ms`, but this difference is not meaningful at this data volume. The composite indexes are appropriate for the expected larger historical price table because they support barcode/store filtering and descending timestamp access.

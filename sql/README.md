# SQL conventions

Numbered execution order. Each file header: purpose, inputs, outputs, KPI/finding it supports.

- `00_*` — schema / staging (`00_views.sql` defines `complaints_core`; run it first — `complaints_raw` itself is created by `src/ingest.py`)
- `05_*` — data quality checks (feed docs/04_data_notes.md)
- `10_*` — core analysis (feed findings F1-F3; KPI-01/02/03 are single aggregates and live here, in the files the dictionary cites)
- `20_*` — composite KPI queries (`20_kpi_within_category_deviation.sql` implements KPI-04, the recommendation)
- `30_*` — dashboard extracts (what Tableau consumes; CSV-export copies of the `10_*` analysis queries, not an evidence source)

Rule: every number in the memo/README traces to exactly one query here (the `30_*` copies don't count as sources).

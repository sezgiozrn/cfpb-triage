# SQL conventions

Numbered execution order. Each file header: purpose, inputs, outputs, KPI/finding it supports.

- `00_*` — schema / staging
- `05_*` — data quality checks (feed docs/04_data_notes.md)
- `10_*` — core analysis (feed findings F1-F3)
- `20_*` — KPI queries (one per dictionary entry, named to match: `20_kpi_time_to_response.sql`)
- `30_*` — dashboard extracts (what Tableau consumes)

Rule: every number in the memo/README traces to exactly one query here.

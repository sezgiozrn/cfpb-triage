# Ingestion

`ingest.py` — CFPB API → local DuckDB. Supports `--from/--to` date window and `--snapshot` pinning for reproducibility.
Keep it boring: requests + pagination + duckdb. This is plumbing, not the portfolio piece.

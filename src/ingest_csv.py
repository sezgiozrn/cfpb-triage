"""
Alternative to ingest.py: load the CFPB bulk CSV export directly.

CFPB publishes the full dataset as a single CSV (multi-GB, updated daily):
  https://www.consumerfinance.gov/data-research/consumer-complaints/search/?dataNormalization=None
  -> "Export" button, or direct download link (check current URL on the page,
     it has changed historically):
  https://files.consumerfinance.gov/ccdb/complaints.csv.zip

This route skips API pagination entirely and lets DuckDB read the CSV
directly with pushdown filtering — much faster for a one-time local pull.
Trade-off: no ingestion-pipeline story for the repo, pure plumbing.
Use this if step 2 of the weekend plan is eating time you want in EDA instead.

Usage:
    python ingest_csv.py --csv complaints.csv --db data/complaints.db \
        --from 2024-01-01 --to 2025-12-31 --snapshot 2026-07-08
"""

import argparse
from datetime import date
from pathlib import Path

import duckdb


def ingest_csv(csv_path: str, db_path: str, date_from: str, date_to: str, snapshot: str | None):
    con = duckdb.connect(db_path)

    # DuckDB reads the CSV directly and filters on the fly — no need to load
    # the full multi-GB file into memory first.
    con.execute(f"""
        CREATE OR REPLACE TABLE complaints AS
        SELECT
            "Complaint ID"              AS complaint_id,
            CAST("Date received" AS DATE)        AS date_received,
            CAST("Date sent to company" AS DATE) AS date_sent_to_company,
            "Product"                   AS product,
            "Sub-product"               AS sub_product,
            "Issue"                     AS issue,
            "Sub-issue"                 AS sub_issue,
            "Company"                   AS company,
            "State"                     AS state,
            "Company response to consumer" AS company_response,
            "Timely response?"          AS timely,
            "Consumer disputed?"        AS consumer_disputed,
            "Consumer consent provided?" AS consumer_consent_provided,
            ("Consumer complaint narrative" IS NOT NULL) AS has_narrative,
            "Tags"                      AS tags,
            "Submitted via"             AS submitted_via
        FROM read_csv_auto('{csv_path}', ALL_VARCHAR=TRUE)
        WHERE CAST("Date received" AS DATE) BETWEEN '{date_from}' AND '{date_to}'
    """)

    row_count = con.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    print(f"Loaded {row_count} rows into {db_path}")

    con.execute("CREATE TABLE IF NOT EXISTS _meta (key VARCHAR, value VARCHAR)")
    con.execute("DELETE FROM _meta WHERE key IN ('pulled_on', 'date_from', 'date_to', 'row_count')")
    con.executemany(
        "INSERT INTO _meta VALUES (?, ?)",
        [
            ("pulled_on", snapshot or date.today().isoformat()),
            ("date_from", date_from),
            ("date_to", date_to),
            ("row_count", str(row_count)),
        ],
    )
    con.close()


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv", required=True, help="Path to downloaded complaints.csv")
    p.add_argument("--db", default="data/complaints.db")
    p.add_argument("--from", dest="date_from", required=True)
    p.add_argument("--to", dest="date_to", required=True)
    p.add_argument("--snapshot", default=None)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    ingest_csv(args.csv, args.db, args.date_from, args.date_to, args.snapshot)

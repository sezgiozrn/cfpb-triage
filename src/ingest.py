"""
CFPB Consumer Complaint Database -> local DuckDB.

Keep it boring: requests + pagination + duckdb. This is plumbing, not the
portfolio piece (see src/README.md).

PAGINATION NOTE (real finding, keep for docs/04_data_notes.md):
The CCDB search API's `frm` offset parameter is broken -- it silently
returns the same first page regardless of value. This is a known, still-open
upstream bug: https://github.com/cfpb/cfpb.github.io/issues/292 (filed
Mar 2025). Verified independently here on 2026-07-08: requesting frm=0,
1000, 5000, 9000 all returned an identical first page. The 10k "depth cap"
warnings this script used to emit were an artifact of that bug (repeatedly
refetching page 1 until frm hit 10000), not real complaint volume.

Working pagination requires `search_after` (an OpenSearch cursor), built
from the `_meta.break_points` object in each response: break_points["2"]
gives [sort_ts, doc_id] for the next page. `frm` must still be sent and
must be a multiple of `size` (API validates this) but no longer functions
as a real offset -- search_after does the actual paging.

SECOND FINDING: break_points is only populated when size<=100. Verified:
size=1000 -> 0 break_point keys (silently stops pagination after page 1,
which is what produced the misleadingly-low "1000 rows for a whole week"
smoke-test result before this was caught). size=100 -> exactly 1 key ("2"),
which is all sequential paging needs. PAGE_SIZE is fixed at 100 for this
reason, not for rate-limiting politeness.
"""

import argparse
import sys
import time
from datetime import datetime, timedelta

import duckdb
import requests

API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
PAGE_SIZE = 100  # must be <=100 -- see SECOND FINDING above
MAX_RETRIES = 4


def fetch_page(date_from: str, date_to: str, frm: int, search_after: str | None,
                state: str | None) -> dict:
    """Returns the raw parsed JSON response (caller pulls hits + break_points)."""
    params = {
        "date_received_min": date_from,
        "date_received_max": date_to,
        "size": PAGE_SIZE,
        "frm": frm,
        "sort": "created_date_asc",
        "no_aggs": "true",
    }
    if state:
        params["state"] = state
    if search_after:
        params["search_after"] = search_after

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data or "non_field_errors" in data:
                raise ValueError(f"API error: {data}")
            return data
        except (requests.RequestException, ValueError) as e:
            wait = 2**attempt
            print(f"  [retry {attempt}/{MAX_RETRIES}] {e} -> sleeping {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch page after {MAX_RETRIES} retries: from={date_from} frm={frm}")


def week_ranges(date_from: str, date_to: str):
    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")
    cur = start
    while cur <= end:
        wk_end = min(cur + timedelta(days=6), end)
        yield cur.strftime("%Y-%m-%d"), wk_end.strftime("%Y-%m-%d")
        cur = wk_end + timedelta(days=1)


def fetch_all_hits(date_from: str, date_to: str, state: str | None):
    """
    Yield all hits for a date window using search_after pagination.

    THIRD FINDING: break_points keys are ABSOLUTE page numbers counted from
    page 1 (the initial frm=0 request), not "next page from wherever you are".
    Page 1's response gives you the cursor for page 2 (key "2"). Page 2's
    response gives you page 3's cursor (key "3") -- NOT another copy of
    page 2's cursor under key "2" again (it does re-include "2", which is
    a trap: reusing it forever refetches the same page->page transition in
    an infinite loop with no progress, which is what happened on the first
    attempt at this). Verified by chaining 3 pages by hand: correct approach
    tracks a page counter and always pulls break_points[str(page_number)].
    """
    page_number = 1
    frm = 0
    search_after = None
    known_break_points: dict = {}

    while True:
        t0 = time.time()
        data = fetch_page(date_from, date_to, frm, search_after, state)
        hits = data.get("hits", {}).get("hits", [])
        print(f"    [page {page_number}] frm={frm} got {len(hits)} hits in {time.time()-t0:.1f}s",
              file=sys.stderr, flush=True)
        if not hits:
            return
        for h in hits:
            yield h

        if len(hits) < PAGE_SIZE:
            return  # last page

        known_break_points.update(data.get("_meta", {}).get("break_points", {}))
        page_number += 1
        next_cursor = known_break_points.get(str(page_number))
        if not next_cursor:
            print(f"    [page {page_number}] no cursor found -- stopping "
                  f"(known keys: {sorted(known_break_points.keys(), key=int)})",
                  file=sys.stderr, flush=True)
            return
        search_after = f"{next_cursor[0]}_{next_cursor[1]}"
        frm += PAGE_SIZE


def ingest(date_from: str, date_to: str, state: str | None, db_path: str, snapshot: str):
    con = duckdb.connect(db_path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS complaints_raw (
            complaint_id VARCHAR PRIMARY KEY,
            product VARCHAR,
            sub_product VARCHAR,
            issue VARCHAR,
            sub_issue VARCHAR,
            company VARCHAR,
            state VARCHAR,
            zip_code VARCHAR,
            date_received TIMESTAMP,
            date_sent_to_company TIMESTAMP,
            company_response VARCHAR,
            timely VARCHAR,
            consumer_disputed VARCHAR,
            submitted_via VARCHAR,
            has_narrative BOOLEAN,
            snapshot VARCHAR,
            ingested_at TIMESTAMP DEFAULT current_timestamp
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ingest_log (
            snapshot VARCHAR,
            date_from VARCHAR,
            date_to VARCHAR,
            state_filter VARCHAR,
            row_count INTEGER,
            run_at TIMESTAMP DEFAULT current_timestamp
        )
    """)

    total = 0
    dupes = 0

    for wk_from, wk_to in week_ranges(date_from, date_to):
        rows = []
        for h in fetch_all_hits(wk_from, wk_to, state):
            s = h.get("_source", {})
            rows.append((
                s.get("complaint_id"), s.get("product"), s.get("sub_product"),
                s.get("issue"), s.get("sub_issue"), s.get("company"), s.get("state"),
                s.get("zip_code"), s.get("date_received"), s.get("date_sent_to_company"),
                s.get("company_response"), s.get("timely"), s.get("consumer_disputed"),
                s.get("submitted_via"), bool(s.get("complaint_what_happened")), snapshot,
            ))

        if rows:
            before = con.execute("SELECT count(*) FROM complaints_raw").fetchone()[0]
            con.executemany(
                "INSERT INTO complaints_raw VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,current_timestamp) "
                "ON CONFLICT (complaint_id) DO NOTHING",
                rows,
            )
            after = con.execute("SELECT count(*) FROM complaints_raw").fetchone()[0]
            inserted = after - before
            dupes += len(rows) - inserted
            total += len(rows)
            print(f"  {wk_from}..{wk_to}: {len(rows)} rows ({inserted} new) "
                  f"(running total {total})")

    con.execute(
        "INSERT INTO ingest_log VALUES (?,?,?,?,?,current_timestamp)",
        [snapshot, date_from, date_to, state or "ALL", total],
    )
    con.close()
    print(f"\nDone. {total} rows fetched, {dupes} duplicate complaint_ids skipped.")
    print(f"Snapshot tag: {snapshot} -> {db_path}")


def main():
    p = argparse.ArgumentParser(description="Pull CFPB complaints into DuckDB")
    p.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    p.add_argument("--state", default=None, help="2-letter state filter, e.g. CA")
    p.add_argument("--db", default="data/complaints.db", help="DuckDB file path")
    p.add_argument("--snapshot", required=True,
                    help="Label for this pull, stamped on every row + ingest_log "
                         "(safe to re-run: dupes skipped on complaint_id)")
    args = p.parse_args()

    print(f"Pulling {args.date_from} -> {args.date_to} "
          f"(state={args.state or 'ALL'}) into {args.db} as snapshot '{args.snapshot}'")
    ingest(args.date_from, args.date_to, args.state, args.db, args.snapshot)


if __name__ == "__main__":
    main()

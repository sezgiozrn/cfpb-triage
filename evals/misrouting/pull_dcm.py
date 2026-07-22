"""
Misrouting audit, step 1: pull the full census of "Debt or credit management"
complaints WITH narratives (CA, extended window) from the CFPB search API.

This is the targeted audit the Phase 2 eval recommended (evals/README.md,
"Next step if pursued"): instead of 50 stratified samples, pull EVERY
DCM complaint with a published narrative and measure what fraction reads
as debt collection (or another misfiled category).

Window is deliberately WIDER than the main analysis (Jan 2024 - Jun 2026 vs
Jan 2024 - Apr 2025): the audit question is about the category's intake
behavior over time, not about reproducing the benchmarking snapshot.

Pagination: same search_after / break_points approach as src/ingest.py --
frm is broken upstream (see ingest.py header), break_points only populate
at size<=100, and cursor keys are absolute page numbers.

Output: evals/misrouting/dcm_narratives.csv
        (complaint_id, date_received, company, issue, sub_product, narrative)
"""

import csv
import sys
import time
from pathlib import Path

import requests

API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
PAGE_SIZE = 100  # break_points only populate at size<=100 (see src/ingest.py)
PRODUCT = "Debt or credit management"
DATE_FROM = "2024-01-01"
DATE_TO = "2026-06-30"
STATE = "CA"
MIN_NARRATIVE_LEN = 50  # same near-empty cutoff as evals/build_sample.py


def fetch_page(frm: int, search_after: str | None) -> dict:
    params = {
        "date_received_min": DATE_FROM,
        "date_received_max": DATE_TO,
        "product": PRODUCT,
        "state": STATE,
        "has_narrative": "true",
        "size": PAGE_SIZE,
        "frm": frm,
        "sort": "created_date_asc",
        "no_aggs": "true",
    }
    if search_after:
        params["search_after"] = search_after
    for attempt in range(1, 5):
        try:
            r = requests.get(API_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            if "error" in data or "non_field_errors" in data:
                raise ValueError(f"API error: {data}")
            return data
        except (requests.RequestException, ValueError) as e:
            wait = 2 ** attempt
            print(f"  [retry {attempt}/4] {e} -> sleeping {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"page fetch failed after 4 retries (frm={frm})")


def fetch_all():
    """Yield every hit, chaining break_points cursors (absolute page keys)."""
    page_number, frm, search_after = 1, 0, None
    known: dict = {}
    while True:
        data = fetch_page(frm, search_after)
        hits = data.get("hits", {}).get("hits", [])
        print(f"  [page {page_number}] {len(hits)} hits", file=sys.stderr, flush=True)
        if not hits:
            return
        yield from hits
        if len(hits) < PAGE_SIZE:
            return
        known.update(data.get("_meta", {}).get("break_points", {}))
        page_number += 1
        cursor = known.get(str(page_number))
        if not cursor:
            print(f"  [page {page_number}] no cursor -- stopping", file=sys.stderr)
            return
        search_after = f"{cursor[0]}_{cursor[1]}"
        frm += PAGE_SIZE
        time.sleep(0.3)


def main():
    out_path = Path(__file__).parent / "dcm_narratives.csv"
    seen: set[str] = set()
    kept = skipped_short = 0
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["complaint_id", "date_received", "company",
                    "issue", "sub_product", "narrative"])
        for h in fetch_all():
            s = h.get("_source", {})
            cid = s.get("complaint_id")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            text = (s.get("complaint_what_happened") or "").strip()
            if len(text) < MIN_NARRATIVE_LEN:
                skipped_short += 1
                continue
            w.writerow([cid, s.get("date_received"), s.get("company"),
                        s.get("issue"), s.get("sub_product"), text])
            kept += 1
    print(f"\nDone. {kept} DCM narratives -> {out_path}")
    print(f"({skipped_short} skipped as near-empty, {len(seen)} unique ids total)")


if __name__ == "__main__":
    main()

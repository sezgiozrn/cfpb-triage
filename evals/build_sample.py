"""
Step 1 of the LLM triage-feasibility eval: build a stratified sample of
complaint narratives.

Sampling design (see evals/README.md for the full method writeup):
- ~50 complaints per product category (10 core categories, credit reporting
  already excluded) = ~500 total. Stratified, NOT proportional: proportional
  sampling would give debt collection ~156 rows and debt/credit management ~3,
  making per-category agreement rates meaningless for small categories.
- IMPORTANT KNOWN BIAS (from docs/04_data_notes.md): narratives exist only
  where the consumer opted in to publish, and opt-in rates vary 25-73% by
  product. This sample represents *complaints with published narratives*,
  not all complaints. The eval writeup must carry this caveat.

Narrative text is not in the local DB (ingest stored only has_narrative),
so this script re-fetches text from the CFPB API per sampled complaint_id
window, using the same search_after pagination as src/ingest.py.

Output: evals/sample.csv (complaint_id, product, narrative)
"""

import csv
import random
import sys
import time
from pathlib import Path

import duckdb
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

API_URL = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
PER_CATEGORY = 50
SEED = 20260709  # fixed seed -> reproducible sample

def fetch_narrative(complaint_id: str) -> str | None:
    """Fetch one complaint's narrative via the direct /{id} endpoint.
    (Verified working 2026-07-09 -- far simpler than search_term filtering.)"""
    for attempt in range(3):
        try:
            r = requests.get(f"{API_URL}{complaint_id}", timeout=30)
            r.raise_for_status()
            d = r.json()
            hits = d.get("hits", {}).get("hits", [])
            src = hits[0].get("_source", {}) if hits else d.get("_source", {})
            return src.get("complaint_what_happened") or None
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


def main():
    random.seed(SEED)
    con = duckdb.connect("data/complaints.db", read_only=True)

    products = [r[0] for r in con.execute(
        "SELECT DISTINCT product FROM complaints_core"
    ).fetchall()]

    out_path = Path("evals/sample.csv")
    rows_written = 0

    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["complaint_id", "product", "narrative"])

        for product in sorted(products):
            ids = [r[0] for r in con.execute(
                "SELECT complaint_id FROM complaints_core "
                "WHERE product = ? AND has_narrative ORDER BY complaint_id",
                [product],
            ).fetchall()]
            # oversample x2 since some fetches will come back empty/missing
            k = min(len(ids), PER_CATEGORY * 2)
            candidates = random.sample(ids, k)

            got = 0
            for cid in candidates:
                if got >= PER_CATEGORY:
                    break
                text = fetch_narrative(cid)
                if text and len(text.strip()) >= 50:  # skip near-empty narratives
                    w.writerow([cid, product, text.strip()])
                    got += 1
                    rows_written += 1
                time.sleep(0.3)  # be polite; this API throttles hard (see data notes)
            print(f"{product}: {got} narratives", flush=True)

    print(f"\nDone. {rows_written} rows -> {out_path}")


if __name__ == "__main__":
    main()

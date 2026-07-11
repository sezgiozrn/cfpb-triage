# Data Notes: CFPB Consumer Complaint Database

## Source

- **Dataset:** CFPB Consumer Complaint Database
- **Access:** Public API — https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/
- **Scope:** California only (`state=CA`)
- **Window pulled:** 2024-01-01 to 2025-04-13 (15.4 months — see ingestion issue #5 for why not the full 2 years)
- **Pulled:** started 2026-07-08, completed 2026-07-09 (long-running pull — see ingestion issue #5)
- **Snapshot tag:** `2026-07-08-ca-2yr` (391,728 rows in `complaints_raw`). The tag is named for the pull's *start date* and *intended* 2-year window; the pull was deliberately stopped at 15.4 months (issue #5). Kept as-is rather than renamed — the tag is baked into the DB rows and renaming a snapshot after the fact is worse than a slightly wrong label with a documented explanation.
- **Analysis scope:** `complaints_core` view = `complaints_raw` WHERE product != 'Credit reporting or other personal consumer reports' (59,291 rows — see data-quality issue #1)

## Schema summary

| Field | Type | % populated | Notes |
|---|---|---|---|
| complaint_id | VARCHAR (PK) | 100% | |
| date_received | TIMESTAMP | 100% | Full second-level precision, not just date |
| date_sent_to_company | TIMESTAMP | 100% | |
| product / sub_product | VARCHAR | 100% / partial | See taxonomy note below |
| company | VARCHAR | 100% | |
| state | VARCHAR | 100% | CA only by design |
| company_response | VARCHAR | 99.9997% | 1 null row out of 391,728 |
| timely | VARCHAR | 100% | |
| has_narrative | BOOLEAN | 100% (derived) | True only if consumer opted in — see bias note |

## Ingestion process issues (API bugs found, not data bugs — real findings, kept for the record)

| # | Issue | Evidence | Decision | Impact |
|---|---|---|---|---|
| 1 | CFPB's `frm` pagination parameter is broken — silently returns page 1 regardless of offset. Confirmed as a known, still-open upstream bug: github.com/cfpb/cfpb.github.io/issues/292 (filed Mar 2025), reproduced independently 2026-07-08 (frm=0/1000/5000/9000 all returned identical results). | Manual API probes, `src/ingest.py` docstring | Switched to `search_after` cursor pagination using `_meta.break_points` from each response | None once fixed — but cost significant dev time to diagnose |
| 2 | `break_points` (the working cursor) is only populated when `size<=100`; at `size=1000` it's empty, silently capping every pull at 1 page. | Direct comparison, sizes 1000/500/100/50/25/10 | Fixed `PAGE_SIZE=100` | Slower ingestion (more requests), but correct |
| 3 | `break_points` keys are absolute page numbers from page 1, not "next page from here" — reusing key `"2"` on every call re-fetches the same page→page2 transition forever (infinite loop, first ingestion attempt hung ~6 min with near-zero CPU before this was caught). | Hand-chained 3 pages, confirmed each response reveals exactly one new key ahead | Track a page counter, always request `break_points[str(page_number)]` | None once fixed |
| 4 | Even with correct pagination, `break_points` lookahead runs dry around page ~100 (100 pages × 100/page = 10,000) on high-volume weeks — the same ~10k ceiling as the original `frm` bug, resurfacing through a different mechanism. | 2 of ~62 weeks pulled hit exactly 10,000 rows with a "no cursor found" log line | Not remediated in this pull (see "What this data can't answer" below) | 2 weeks (2025-01-13 to 2025-01-26) are undercounted; flagged, not fixed |
| 5 | Runtime ballooned from an initial ~1s/page pace to 9h40m wall-clock for 63/104 weeks (mostly network wait, not CPU — the API appears to throttle sustained sessions heavily). | `ps` elapsed vs. CPU time comparison mid-run | Stopped the pull deliberately at 15.4 months instead of the full 2 years (see decision memo framing) rather than burn ~6 more hours for diminishing-returns data | Window ends 2025-04-13, not 2025-12-31 |
| 6 | Three earlier debug/smoke-test runs (national scope, pre-dating the `--state CA` fix) wrote 11,000 non-CA rows into the same DuckDB table before the real pull started, since the table was never dropped between attempts. | `SELECT state, COUNT(*) ... WHERE state != 'CA'` found rows from ~45 other states | Deleted all rows outside snapshot `2026-07-08-ca-2yr`, confirmed 0 non-CA rows remain | None post-cleanup — but this is exactly the kind of silent contamination a real pipeline needs a check for, not just a one-off fix |

## Quality issues in the data itself

| # | Issue | Evidence | Decision | Impact on findings |
|---|---|---|---|---|
| 1 | **Credit reporting complaints dominate the dataset (84.9%, 332,437 of 391,728 rows).** This is a known real-world pattern (mass-filed disputes against the 3 credit bureaus), not an ingestion artifact. | `sql/05_dq_taxonomy_drift.sql` product breakdown | Excluded "Credit reporting or other personal consumer reports" from the core analysis scope (`complaints_core` view, 59,291 rows) — it would otherwise drown out every other product's signal in any stall-rate or volume finding | Analysis scope is now the ~15% of complaints tied to banking, cards, loans, debt collection, and money transfer — more operationally diverse, better fit for a triage-workflow story |
| 2 | Narrative availability (consumer opted in to publish their story) varies sharply by product: 25.3% for credit reporting vs. 73.1% for money transfer, 29.6% overall. | `sql/05_dq_narrative_bias.sql` | Any Phase-2 LLM classification eval sampling from narratives is NOT a representative sample of all complaints — flagging now before `evals/` gets built | Narrative-based findings must be scoped explicitly to "complaints with narratives," not generalized to all complaints |
| 3 | **Duplicate check: clean.** 0 duplicate complaint_ids across all 391,728 rows; near-duplicate probe (same company + same date_received timestamp + same product, threshold >20) returned 0 clusters. Run 2026-07-09 against the final snapshot, post issue-#6 cleanup. | `sql/05_dq_duplicates.sql` | No remediation needed — recorded so the check doesn't read as unrun | None — confirms the retry-safe pagination didn't double-insert pages |
| 4 | Monthly complaint volume rises steadily from ~14k (Jan 2024) to a peak of ~40k (Jan 2025), with an irregular dip in Feb 2025 and a partial, lower count in Apr 2025 (data cutoff mid-month). | `sql/05_dq_coverage.sql` monthly breakdown | Not yet explained — could be real growth, could be a publication-lag artifact (CFPB publishes complaints only after company response or 15 days, so the most recent ~2-4 weeks of any pull will always undercount) | Treat the most recent 3-4 weeks of the window (mid-March through April 13, 2025) as provisionally undercounted until checked in EDA; don't use them for a trend-line finding without that caveat |

## Known biases & limitations

- Complaints ≠ incidents: this measures who complained to a federal regulator, not underlying financial-service failure rates. Self-selection is real and unmeasured here.
- Company response categories are coarse and company-chosen, not independently verified by CFPB.
- CA-only scope (deliberate, see ingestion issue #5) — findings describe California consumer complaints, not a national pattern, though CA is a large enough market to be directionally informative for a CA-headquartered or CA-focused triage redesign.
- Two specific weeks (2025-01-13 to 2025-01-26) are undercounted due to the API's ~10k pagination ceiling (see ingestion issue #4) — exclude or caveat any finding that leans on that specific date range.
- **`consumer_disputed` is 100% NULL across all 59,291 core-scope rows** (confirmed via `SELECT DISTINCT`). This is not a pull error — CFPB stopped populating the "Consumer disputed?" field around 2017 when they changed their complaint-handling process. The field is structurally dead for this entire date window and cannot support a KPI. Dropped from consideration in the KPI dictionary.

## What this data CAN'T answer

- Whether excluded credit-reporting complaints follow the same or different stall/triage patterns as the core scope — that's a separate, unstarted analysis.
- National patterns — this is CA-only by design.
- True complaint *rates* (complaints per transaction or per customer) — only raw complaint counts are available here, no denominator.

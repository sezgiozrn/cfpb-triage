# CFPB Complaint Triage — Servicer Benchmarking Methodology

> A naive portfolio-wide relief-rate comparison flags the wrong company. Using
> 391,728 real CA consumer complaints (Jan 2024–Apr 2025), this project finds why,
> and what to compare against instead.

**Deliverables:** [Decision Memo](docs/01_decision_memo.md) · [BRD](docs/02_brd.md) · [KPI Dictionary](docs/03_kpi_dictionary.md) · [Data Notes](docs/04_data_notes.md) · [Live Dashboard](https://public.tableau.com/app/profile/sez.ozrn/viz/CFPBCAServicerBenchmarking/Dashboard1)

---

## The 3-minute version

**Problem.** Companies handling consumer financial complaints are often benchmarked
against a single portfolio-wide "relief rate" target. Does that comparison actually
identify real service-quality problems, or does it just reflect which product a
company happens to service?

**Approach.** Pulled 391,728 real CFPB consumer complaints for California (Jan
2024–Apr 2025) via CFPB's public API, cleaned and scoped the data (excluded credit
reporting — 84.9% of volume, a separate workflow), and analyzed relief and
timely-response rates by product and by company using SQL (DuckDB).

**Findings.**
1. Relief rate varies **14x by product alone** — 2.6% (student loan) to 36.8%
   (credit card) — before any company-level effect is considered.
2. A naive company-vs-portfolio-average comparison flagged **MOHELA** as a poor
   performer (2.8% relief vs. 23.4% portfolio average). That's a false positive:
   MOHELA is roughly mid-pack **within its own product category** — 4 of 8 major
   student loan servicers show 0.0% relief.
3. The real, evidence-backed outlier is **EdFinancial Services**: 50.7% timely
   response, about half of every peer servicer (88–100%), while still granting 0%
   relief.
4. **AI-assisted feasibility check:** an LLM classification eval on 500 real complaint
   narratives (79.8% overall agreement with official categories) surfaced a likely
   intake-labeling problem, not a model-accuracy problem — one category ("Debt or
   credit management," 44% agreement) appears to absorb misfiled debt-collection
   complaints. Full method and hand-inspected examples in
   [evals/README.md](evals/README.md).

**Recommendation.** Replace portfolio-wide comparison with within-product-category
benchmarking (KPI-04). Pilot on the student loan category (8 servicers, already
scoped) for one quarter before extending. Full case in the
[decision memo](docs/01_decision_memo.md).

---

## Repo map

| Path | What it is |
|---|---|
| `docs/01_decision_memo.md` | 1-page recommendation, with the corrected finding and why the naive comparison failed |
| `docs/02_brd.md` | Requirements for a within-category servicer scorecard |
| `docs/03_kpi_dictionary.md` | 4 KPIs, including the mandatory product-stratification rule for relief rate |
| `docs/04_data_notes.md` | 6 real API/ingestion bugs found (incl. a currently-open upstream CFPB bug) + 3 data-quality findings |
| `sql/05_dq_*.sql` | Data quality checks: coverage, duplicates, taxonomy drift, narrative bias |
| `sql/10_*.sql` | Core analysis: routing/timeliness, relief outcomes |
| `src/ingest.py` | CA-scoped CFPB API ingestion (search_after pagination, documented API workarounds) |

## A note on how this was built

This project hit a real methodological trap and corrected course in the open rather
than quietly fixing it: an early cut of the analysis compared each company's relief
rate against a pooled "all other companies" average, which flagged MOHELA as an
outlier. Checking that finding against product-level base rates (not just
company-level) showed the comparison was confounded — student loan servicing is
structurally low-relief across the board, not specific to MOHELA. The corrected
analysis, which controls for product category, is what's reflected in the memo and
BRD. The near-miss itself is documented in `docs/03_kpi_dictionary.md`'s change log
and `docs/04_data_notes.md`, since knowing what comparison NOT to make is as much a
BA finding as the final recommendation.

## Reproducing

```bash
pip install -r requirements.txt
python src/ingest.py --from 2024-01-01 --to 2025-12-31 --state CA --db data/complaints.db --snapshot my-pull
# then run sql/05_*.sql and sql/10_*.sql against data/complaints.db (DuckDB)
```

## Data source & caveats

CFPB Consumer Complaint Database (public, updated daily):
https://www.consumerfinance.gov/data-research/consumer-complaints/search/

- **CA only** (deliberate scope decision — see data notes)
- **Jan 2024–Apr 2025**, not the full 2 years (stopped deliberately after a 15.4-month
  pull rather than burn ~6 more hours for diminishing-returns data — see data notes)
- Complaints ≠ incidents: this measures who complained to a federal regulator, not
  underlying service-failure rates
- Full caveat list in [docs/04_data_notes.md](docs/04_data_notes.md)

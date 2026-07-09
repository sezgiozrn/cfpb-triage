# Decision Memo: Add Product-Category Benchmarking to Servicer Complaint Review

**To:** VP, Consumer Response Operations
**From:** Sezgi Ozturan, Business Analyst
**Date:** 2026-07-09
**Decision requested:** Approve building a within-product-category servicer scorecard
(vs. the current practice of comparing servicers against a single portfolio-wide
relief-rate target)

---

## Recommendation

Stop comparing complaint-handling outcomes across companies using a single
portfolio-wide relief rate. It produces false positives. Instead, benchmark each
company only against peers in its own product category, and flag deviations from
*that* baseline. This CA CFPB dataset shows exactly how the current approach fails,
and exactly which company it would have wrongly flagged.

## The problem, quantified

Relief rate (share of complaints closed with monetary or non-monetary relief) varies
14x by product alone — 2.6% for student loans vs. 36.8% for credit cards — before any
company-level effect is considered (KPI-02, `sql/10_relief_outcomes.sql`). A
portfolio-wide comparison naively flagged MOHELA (939 CA student-loan complaints,
2.8% relief rate) as an outlier against an "all other companies" pool averaging 23.4%
relief. That comparison is wrong: **student loan is structurally the lowest-relief
product in the entire dataset**, and MOHELA's rate is in line with its own peers
(Nelnet 0.0%, Maximus 0.0%, Navient 0.6%). Flagging MOHELA on this basis would waste
review effort on a company that isn't actually deviating from its category.

## Evidence

1. Relief rate by product ranges from 2.6% (student loan) to 36.8% (credit card) —
   a structural difference in what "relief" means per product, not a quality signal
   (`sql/10_relief_outcomes.sql`).
2. Within student loan specifically, 4 of 8 servicers with sufficient volume show
   0.0% relief (Maximus, EdFinancial, Nelnet, and the Federal Student Aid contractor)
   — MOHELA's 2.8% is roughly mid-pack, not a low outlier (`sql/10_relief_outcomes.sql`).
3. The real company-level outlier is **EdFinancial Services**: 50.7% timely-response
   rate, roughly half of every peer servicer in the category (88–100%), while still
   granting 0% relief (`sql/10_relief_outcomes.sql`, student-loan servicer breakdown).

## Options considered

| Option | Cost/effort | Expected impact | Why / why not |
|---|---|---|---|
| Do nothing (keep portfolio-wide comparison) | None | Continues generating false-positive flags on structurally low-relief products (student loans, mortgages, money transfer) while missing real outliers like EdFinancial | Cheapest, but actively misdirects review effort |
| **Recommended: within-category benchmarking (KPI-04)** | Low — same underlying data, different grouping logic in the KPI query | Correctly identifies EdFinancial-style outliers; stops flagging structurally-low-relief products as if they were badly-run ones | Requires updating the KPI definition and any existing dashboard/report built on the flat portfolio-wide rate |
| Build a full statistical control model (regression adjusting for product, complaint type, region) | High — new modeling work, ongoing maintenance | Marginal accuracy gain over simple within-category peer comparison at this data volume | Not justified yet; revisit if false-positive/negative rates on the simple version prove too high in practice |

## Risks & open questions

- **n=57 for the Federal Student Aid contractor entry is thin** — its 0% relief and
  0% timely rate is a striking combination but shouldn't be acted on without a larger
  sample or a longer date window.
- Federal student loan servicers operate under different, more constrained relief
  authority than banks or private lenders by regulation — some of the category-wide
  low relief rate may be a genuine structural ceiling, not a solvable service-quality
  problem. Within-category benchmarking controls for this at the category level, but
  can't fully separate "structurally constrained" from "poorly run" at the
  individual-servicer level without a longer time series or a second data source.
- This analysis is CA-only; whether EdFinancial's timeliness gap holds nationally is
  unverified.

## Next step

Pilot the within-category scorecard on the student loan product category (8 servicers,
already scoped) for one quarter, using KPI-04 as defined in the KPI dictionary, before
extending to the other 9 product categories.

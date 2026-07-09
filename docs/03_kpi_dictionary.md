# KPI Dictionary

**Scope:** All metrics below are computed on `complaints_core` (CFPB CA complaints,
2024-01-01 to 2025-04-13, credit-reporting complaints excluded — see
docs/04_data_notes.md for why).
**Grain convention:** All rates computed at complaint level unless stated.
**Refresh:** One-time analysis; not a live-refreshed dashboard.

---

## KPI-01: Timely Response Rate

| Field | Definition |
|---|---|
| **Business question** | Which products/companies fail to respond to CFPB within the required window? |
| **Definition (plain English)** | Share of complaints where the company's response was marked timely by CFPB. |
| **Formula** | `COUNT(*) FILTER (WHERE timely = 'Yes') / COUNT(*)` |
| **Grain** | product, or company |
| **Source query** | `sql/10_routing_and_timeliness.sql` |
| **Inclusions / exclusions** | All core-scope complaints. No exclusion for company size — see Known limitations. |
| **Edge cases** | None found — `timely` is 100% populated in this scope. |
| **Known limitations** | Rates for companies with very low volume (<20 complaints) are noisy — a single late response can swing the rate by several points. Compare only companies with n>=20 within a product category, and always cite n alongside the rate. |
| **Owner** | Ops/compliance analyst |

## KPI-02: Relief Rate

| Field | Definition |
|---|---|
| **Business question** | How often does a complaint actually result in relief for the consumer, vs. just an explanation? |
| **Definition (plain English)** | Share of complaints closed with monetary or non-monetary relief (combined), out of all complaints. |
| **Formula** | `COUNT(*) FILTER (WHERE company_response IN ('Closed with monetary relief','Closed with non-monetary relief')) / COUNT(*)` |
| **Grain** | product, or company within product |
| **Source query** | `sql/10_relief_outcomes.sql` |
| **Inclusions / exclusions** | Monetary and non-monetary relief are combined into one rate. Excludes "Closed with explanation" and "Untimely response" from the numerator. |
| **Edge cases** | None found — `company_response` is 99.9997% populated (1 null row). |
| **Known limitations** | **Critical: this KPI must never be compared across products without controlling for product.** Relief rate varies 14x by product alone (2.6% for student loan vs. 36.8% for credit card) before any company-level effect is considered — this is a structural difference in what "relief" even means per product (e.g., a credit bureau correcting a report entry vs. a bank issuing a refund are very different asks), not a quality signal. **Rule: only compare relief rate within the same product category.** A cross-product comparison that doesn't control for this produced a materially wrong headline finding during this project's own EDA (see docs/04_data_notes.md) — kept as a documented near-miss, not scrubbed from the record. |
| **Owner** | Ops/compliance analyst |

## KPI-03: Days to Route

| Field | Definition |
|---|---|
| **Business question** | How long does CFPB's own internal triage step (received → sent to company) take, and where does it stall? |
| **Definition (plain English)** | Calendar days between complaint received and complaint sent to the company. |
| **Formula** | `date_diff('day', date_received, date_sent_to_company)`, aggregated as median and p90 |
| **Grain** | complaint, aggregated to product |
| **Source query** | `sql/10_routing_and_timeliness.sql` |
| **Inclusions / exclusions** | All core-scope complaints. |
| **Edge cases** | Heavily right-skewed: 87.8% of complaints route same-day (0 days); the median is uninformative on its own. Always report alongside p90 or the long-tail count, never median alone. |
| **Known limitations** | This measures CFPB's internal routing step, not the company's resolution time — there is no explicit "resolved" date in this dataset, only `date_sent_to_company` and the final `company_response` category. |
| **Owner** | Ops analyst |

## KPI-04: Within-Category Servicer Deviation

| Field | Definition |
|---|---|
| **Business question** | Given KPI-02's product-confound, which individual companies deviate from their *own product category's* peer average — the actual outlier-detection question this project needs? |
| **Definition (plain English)** | A company's KPI-01 or KPI-02 value, compared only against other companies in the same product category with sufficient volume, not against the portfolio-wide average. |
| **Formula** | Company rate vs. product-category median rate, computed only for companies with n>=20 within that product |
| **Grain** | company, within product |
| **Source query** | `sql/10_relief_outcomes.sql` (student loan servicer breakdown) |
| **Inclusions / exclusions** | n>=20 threshold to exclude noisy small-sample companies (see KPI-01 limitations) |
| **Edge cases** | Products with very few companies (e.g., a near-monopoly servicer) don't have a meaningful peer set — flag rather than compute a "deviation" for those. |
| **Known limitations** | This is the KPI that actually answers the project's decision question. KPI-02 alone, without this stratification, produces a false positive (see decision memo for the corrected finding). |
| **Owner** | Ops/compliance analyst |

## Candidate KPIs considered and dropped

- **Consumer dispute rate** — dropped entirely. `consumer_disputed` is 100% NULL in this dataset; CFPB stopped populating this field around 2017. See docs/04_data_notes.md.

## Change log

| Date | KPI | Change | Reason |
|---|---|---|---|
| 2026-07-09 | KPI-02 | Added mandatory product-stratification rule to Known limitations | A naive company-vs-portfolio-average comparison (MOHELA vs. "all others" pooled) produced a headline finding that didn't survive a product-level and within-category check — MOHELA turned out to be typical for its product, not an outlier. Corrected before it reached the memo. |

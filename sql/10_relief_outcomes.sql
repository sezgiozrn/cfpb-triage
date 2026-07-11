-- 10_relief_outcomes.sql
-- Purpose: relief-rate findings F1-F3, the core of the decision memo.
-- Feeds KPI-02 in docs/03_kpi_dictionary.md. (KPI-03 lives in
-- 10_routing_and_timeliness.sql; KPI-04 in 20_kpi_within_category_deviation.sql.)

-- Overall outcome distribution (core scope)
SELECT company_response, COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM complaints_core
GROUP BY 1 ORDER BY n DESC;

-- F1: relief rate by product — the 14x variation (2.6% student loan vs.
-- 36.8% credit card) that makes any cross-product comparison invalid.
-- This is the memo's "problem, quantified" number and KPI-02's
-- mandatory-stratification rationale.
SELECT
    product,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) FILTER (
        WHERE company_response IN ('Closed with monetary relief', 'Closed with non-monetary relief')
    ) / COUNT(*), 1) AS pct_relief
FROM complaints_core
GROUP BY 1
ORDER BY pct_relief ASC;

-- THE DOCUMENTED NEAR-MISS — kept deliberately, do not treat as a finding.
-- This is the naive portfolio-wide comparison that wrongly flagged MOHELA
-- (2.8% relief vs. 23.4% pooled "all others") during EDA. It is confounded
-- by product mix — see the F1 query above and KPI-02's stratification rule.
-- Preserved because knowing what comparison NOT to make is the project's
-- central lesson (docs/03_kpi_dictionary.md change log, docs/04_data_notes.md).
SELECT
    CASE WHEN company = 'MOHELA' THEN 'MOHELA' ELSE 'all others' END AS grp,
    company_response,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY
        CASE WHEN company = 'MOHELA' THEN 'MOHELA' ELSE 'all others' END), 1) AS pct
FROM complaints_core
GROUP BY 1, 2 ORDER BY 1, n DESC;

-- F2 + F3: student-loan servicer breakdown — relief AND timely, within one
-- product category (the corrected comparison). n>=20 per KPI-01 known
-- limitations / BR-02, matching the dashboard scorecard and KPI-04 threshold.
-- F2: 4 of 8 servicers at 0.0% relief; MOHELA (2.8%) is mid-pack, not an outlier.
-- F3: EdFinancial Services at 50.7% timely vs. an 88-100% peer range.
SELECT
    company,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) FILTER (WHERE timely = 'Yes') / COUNT(*), 1) AS pct_timely,
    ROUND(100.0 * COUNT(*) FILTER (
        WHERE company_response IN ('Closed with monetary relief', 'Closed with non-monetary relief')
    ) / COUNT(*), 1) AS pct_relief
FROM complaints_core
WHERE product = 'Student loan'
GROUP BY 1
HAVING COUNT(*) >= 20
ORDER BY pct_relief ASC;

-- Relief rate by company, pooled across products — CONTEXT ONLY. Per KPI-02's
-- stratification rule this ranking must never drive a review flag (a company's
-- position here mostly reflects its product mix). Kept to show what the naive
-- view looks like next to the stratified one.
SELECT
    company,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) FILTER (
        WHERE company_response IN ('Closed with monetary relief', 'Closed with non-monetary relief')
    ) / COUNT(*), 1) AS pct_any_relief
FROM complaints_core
GROUP BY 1
HAVING COUNT(*) >= 200
ORDER BY pct_any_relief ASC;

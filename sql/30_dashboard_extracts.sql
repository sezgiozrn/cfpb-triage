-- 30_dashboard_extracts.sql
-- Purpose: pre-aggregated extracts for the Tableau dashboard. Two views,
-- matching the memo's two-part story: (1) why product-level context
-- matters, (2) the actual within-category scorecard.
-- NOTE: these are CSV-export copies of the analysis queries in
-- 10_relief_outcomes.sql (F1 and F2/F3). The memo's evidence traces to the
-- 10_ file; this file only exists so Tableau has clean inputs.

-- Extract 1: relief rate by product (motivates the whole methodology fix --
-- this is the 14x variation that made the naive comparison wrong)
SELECT
    product,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) FILTER (
        WHERE company_response IN ('Closed with monetary relief', 'Closed with non-monetary relief')
    ) / COUNT(*), 1) AS pct_relief
FROM complaints_core
GROUP BY 1
ORDER BY pct_relief ASC;

-- Extract 2: student loan servicer scorecard (the actual pilot from the BRD) --
-- includes both KPI-01 (timely) and KPI-02 (relief), n>=20 threshold per
-- KPI dictionary's noise-control rule
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

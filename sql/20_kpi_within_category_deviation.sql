-- 20_kpi_within_category_deviation.sql
-- Purpose: implements KPI-04 (Within-Category Servicer Deviation) — the
-- project's actual recommendation. Company rates compared ONLY against
-- same-product-category peers with n>=20, never the portfolio-wide pool.
-- Feeds KPI-04 in docs/03_kpi_dictionary.md; BR-01..BR-04 in docs/02_brd.md.
--
-- Flag rule (BR-04 starting point): strictly below the category's bottom
-- quartile on relief OR timely rate. Strict `<` (not `<=`) is deliberate:
-- in structurally-zero-relief categories (student loan: 4 of 8 servicers
-- tied at 0.0% relief, q25 = 0.0), `<=` would flag half the category on a
-- meaningless tie. Threshold tuning is BRD open question #1.
--
-- Verified against snapshot 2026-07-08-ca-2yr (2026-07-09):
--   292 qualifying company-product pairs, 72 flagged, 0 no-peer-set cases.
--   Student loan category: flags EdFinancial Services (timely 50.7 vs.
--   category median 99.9) and the FSA contractor (0.0/0.0, n=57 — thin,
--   see memo risks); MOHELA (2.8% relief, 88.4% timely) is NOT flagged —
--   the false positive this KPI exists to eliminate.

WITH company_rates AS (
    SELECT product, company, COUNT(*) AS n,
        ROUND(100.0 * COUNT(*) FILTER (WHERE timely = 'Yes') / COUNT(*), 1) AS pct_timely,
        ROUND(100.0 * COUNT(*) FILTER (WHERE company_response IN
            ('Closed with monetary relief', 'Closed with non-monetary relief')
        ) / COUNT(*), 1) AS pct_relief
    FROM complaints_core
    GROUP BY 1, 2
    HAVING COUNT(*) >= 20  -- noise control, per KPI-01 known limitations / BR-02
),
peer_stats AS (
    SELECT *,
        COUNT(*)                        OVER (PARTITION BY product) AS peer_count,
        MEDIAN(pct_relief)              OVER (PARTITION BY product) AS cat_median_relief,
        MEDIAN(pct_timely)              OVER (PARTITION BY product) AS cat_median_timely,
        quantile_cont(pct_relief, 0.25) OVER (PARTITION BY product) AS cat_q25_relief,
        quantile_cont(pct_timely, 0.25) OVER (PARTITION BY product) AS cat_q25_timely
    FROM company_rates
)
SELECT product, company, n, peer_count,
    pct_relief, cat_median_relief,
    ROUND(pct_relief - cat_median_relief, 1) AS relief_deviation,
    pct_timely, cat_median_timely,
    ROUND(pct_timely - cat_median_timely, 1) AS timely_deviation,
    CASE
        -- KPI-04 edge case: near-monopoly products have no meaningful peer
        -- set — flag as not-comparable rather than compute a "deviation"
        WHEN peer_count < 2 THEN 'NO PEER SET - not comparable'
        WHEN pct_relief < cat_q25_relief
          OR pct_timely < cat_q25_timely THEN 'FLAG - bottom quartile in category'
        ELSE 'ok'
    END AS review_flag
FROM peer_stats
-- WHERE product = 'Student loan'  -- uncomment for the BRD pilot scope
ORDER BY product, pct_relief ASC, pct_timely ASC;

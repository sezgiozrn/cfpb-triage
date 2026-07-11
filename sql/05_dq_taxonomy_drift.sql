-- 05_dq_taxonomy_drift.sql
-- Purpose: CFPB has changed product/sub-product category names over time.
-- If your date window spans a taxonomy change, trend analysis by product
-- will be silently wrong (a category "disappearing" might just be a rename).
-- Run before any finding that compares product volumes across months.

-- Does each product name persist across the full date range, or does it
-- appear/disappear abruptly? Abrupt appearance/disappearance is the signal.
SELECT
    product,
    MIN(date_received) AS first_seen,
    MAX(date_received) AS last_seen,
    COUNT(*) AS n
FROM complaints_raw
GROUP BY product
ORDER BY first_seen;

-- Same check one level down, for sub_product — this is where taxonomy
-- churn usually actually happens (product names are more stable)
SELECT
    product,
    sub_product,
    MIN(date_received) AS first_seen,
    MAX(date_received) AS last_seen,
    COUNT(*) AS n
FROM complaints_raw
WHERE sub_product IS NOT NULL
GROUP BY product, sub_product
ORDER BY product, first_seen;

-- ACTION: if any product/sub_product shows a hard cutover (first_seen or
-- last_seen landing mid-window with no gradual taper), log it in
-- docs/04_data_notes.md and decide: exclude the transition period,
-- collapse old/new names into one category, or scope the analysis window
-- to avoid the boundary entirely.

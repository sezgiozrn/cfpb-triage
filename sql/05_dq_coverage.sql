-- 05_dq_coverage.sql
-- Purpose: sanity-check the pull before trusting anything downstream.
-- Run first, always. Feeds docs/04_data_notes.md "quality issues" table.

-- Row count and date range actually landed vs. what was requested
SELECT
    MIN(date_received) AS earliest,
    MAX(date_received) AS latest,
    COUNT(*)            AS total_rows,
    COUNT(DISTINCT complaint_id) AS distinct_ids
FROM complaints;

-- Monthly volume — eyeball for gaps or suspicious cliffs (API pagination
-- bugs and CSV truncation both show up here first)
SELECT
    date_trunc('month', date_received) AS month,
    COUNT(*) AS n
FROM complaints
GROUP BY 1
ORDER BY 1;

-- Null rate on every field the KPIs will depend on — do this before
-- writing a single KPI query, not after
SELECT
    COUNT(*) FILTER (WHERE date_received IS NULL)         AS null_date_received,
    COUNT(*) FILTER (WHERE date_sent_to_company IS NULL)  AS null_date_sent,
    COUNT(*) FILTER (WHERE product IS NULL)               AS null_product,
    COUNT(*) FILTER (WHERE company IS NULL)                AS null_company,
    COUNT(*) FILTER (WHERE company_response IS NULL)      AS null_response,
    COUNT(*) FILTER (WHERE timely IS NULL)                 AS null_timely
FROM complaints;

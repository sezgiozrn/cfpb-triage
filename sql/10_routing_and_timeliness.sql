-- 10_routing_and_timeliness.sql
-- Purpose: baseline triage metrics on the core scope (credit reporting excluded).
-- Feeds KPI-01, KPI-03 in docs/03_kpi_dictionary.md

-- Days to route (received -> sent to company), by product
SELECT
    product,
    MEDIAN(date_diff('day', date_received, date_sent_to_company)) AS median_route_days,
    quantile_cont(date_diff('day', date_received, date_sent_to_company), 0.9) AS p90_route_days,
    COUNT(*) AS n
FROM complaints_core
GROUP BY 1 ORDER BY median_route_days DESC;

-- Timely response rate by product (KPI-01)
SELECT
    product,
    COUNT(*) AS total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE timely = 'Yes') / COUNT(*), 1) AS pct_timely
FROM complaints_core
GROUP BY 1 ORDER BY pct_timely ASC;

-- 10_relief_outcomes.sql
-- Purpose: relief-rate finding, the core of the decision memo.
-- Feeds KPI-02, KPI-03 in docs/03_kpi_dictionary.md and the memo's headline finding.

-- Overall outcome distribution (core scope)
SELECT company_response, COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM complaints_core
GROUP BY 1 ORDER BY n DESC;

-- MOHELA vs. all other companies: outcome distribution (THE finding)
SELECT
    CASE WHEN company = 'MOHELA' THEN 'MOHELA' ELSE 'all others' END AS grp,
    company_response,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY
        CASE WHEN company = 'MOHELA' THEN 'MOHELA' ELSE 'all others' END), 1) AS pct
FROM complaints_core
GROUP BY 1, 2 ORDER BY 1, n DESC;

-- Student loan servicer comparison: timely rate + volume (context for the MOHELA finding)
SELECT
    company,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) FILTER (WHERE timely = 'Yes') / COUNT(*), 1) AS pct_timely
FROM complaints_core
WHERE product = 'Student loan'
GROUP BY 1
HAVING COUNT(*) >= 50
ORDER BY n DESC;

-- Relief rate specifically (monetary + non-monetary combined) by company, for context
-- among companies with enough volume to compare fairly
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

-- 05_dq_duplicates.sql
-- Purpose: catch duplicate complaint_ids before they inflate any KPI.
-- Real risk with the API route especially — pagination re-runs after a
-- retry can double-insert a page if not handled carefully.

-- Exact duplicate IDs
SELECT
    complaint_id,
    COUNT(*) AS n
FROM complaints_raw
GROUP BY complaint_id
HAVING COUNT(*) > 1
ORDER BY n DESC;

-- Sanity total: should be 0 if ingestion is clean
SELECT COUNT(*) AS duplicate_id_count
FROM (
    SELECT complaint_id
    FROM complaints_raw
    GROUP BY complaint_id
    HAVING COUNT(*) > 1
);

-- Near-duplicates worth a look even if IDs are unique: same company + same
-- date_received + same product could indicate an upstream data issue
-- (or just a busy company on a busy day — check before assuming it's noise)
SELECT
    company, date_received, product,
    COUNT(*) AS n
FROM complaints_raw
GROUP BY company, date_received, product
HAVING COUNT(*) > 20
ORDER BY n DESC
LIMIT 20;

-- 05_dq_narrative_bias.sql
-- Purpose: the complaint narrative field only exists when the consumer
-- opts in (consumer_consent_provided). If Phase 2 (LLM eval) samples from
-- narratives, that sample is NOT representative of all complaints —
-- document this now so it doesn't get silently forgotten by the time
-- evals/ gets built.

-- What fraction of complaints have a narrative at all?
SELECT
    has_narrative,
    COUNT(*) AS n,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
FROM complaints
GROUP BY has_narrative;

-- Does narrative availability skew by product? (If complaint types that
-- opt in to narratives are systematically different, any narrative-based
-- finding needs that caveat explicitly in docs/04_data_notes.md)
SELECT
    product,
    COUNT(*) AS total,
    COUNT(*) FILTER (WHERE has_narrative) AS with_narrative,
    ROUND(100.0 * COUNT(*) FILTER (WHERE has_narrative) / COUNT(*), 1) AS pct_with_narrative
FROM complaints
GROUP BY product
ORDER BY total DESC;

-- Does it skew by state? (proxy check for regional consent-rate bias)
SELECT
    state,
    COUNT(*) AS total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE has_narrative) / COUNT(*), 1) AS pct_with_narrative
FROM complaints
WHERE state IS NOT NULL
GROUP BY state
ORDER BY total DESC
LIMIT 15;

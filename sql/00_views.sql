-- 00_views.sql
-- Purpose: schema/staging — defines the analysis scope every other query
-- depends on. Run this once against data/complaints.db before any 05_/10_/20_
-- query. (complaints_raw itself is created by src/ingest.py.)
--
-- Why the exclusion: credit-reporting complaints are 84.9% of raw volume
-- (332,437 of 391,728 rows) — mass-filed bureau disputes that would drown
-- every other product's signal. See docs/04_data_notes.md, quality issue #1.

CREATE VIEW IF NOT EXISTS complaints_core AS
SELECT *
FROM complaints_raw
WHERE product != 'Credit reporting or other personal consumer reports';

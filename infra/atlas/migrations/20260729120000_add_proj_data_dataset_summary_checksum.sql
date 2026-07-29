-- Surface the Dataset checksum on the read model, as ingest's natural key.
--
-- `ingest_scan` refuses to ingest bytes CORA already holds, and the
-- checksum is the natural key for that refusal: the same file is
-- legitimately multi-homed across storage tiers, so its URI changes
-- while its digest does not. Until now no queryable checksum surface
-- existed anywhere: this table had no checksum column, and the
-- distribution summary stores checksum as nested JSON with no filtering
-- query. Without the pre-check this column backs, pointing CORA at the
-- same file twice silently duplicates the whole
-- Dataset/Distribution/Acquisition chain, because register_dataset
-- mints a fresh UUID per call and its AlreadyExists guard is
-- defensively unreachable.
--
-- Additive forward-only migration:
--   - Columns are nullable: the values come from the DatasetRegistered
--     genesis payload (both fields required there since inception), so
--     every row written after this migration carries them; rows
--     projected before it hold NULL until a projection rebuild, and a
--     NULL never equality-matches a probe, so the pre-check simply
--     cannot vouch for pre-migration rows until rebuilt.
--   - Composite index (checksum_algorithm, checksum_value) backs the
--     digest-equality probe `WHERE checksum_algorithm = $1 AND
--     checksum_value = $2`.
--
-- The projection's `apply()` for `DatasetRegistered` is updated in the
-- same commit (`cora.data.projections.summary._INSERT_DATASET_SQL`).

ALTER TABLE proj_data_dataset_summary
    ADD COLUMN checksum_algorithm TEXT,
    ADD COLUMN checksum_value TEXT;

CREATE INDEX proj_data_dataset_summary_checksum_idx
    ON proj_data_dataset_summary (checksum_algorithm, checksum_value);

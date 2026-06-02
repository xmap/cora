-- Drop UNIQUE INDEX on `proj_equipment_model_summary (manufacturer_name, part_number)`.
--
-- The original Model summary migration (20260601110000) created this
-- UNIQUE INDEX to materialize the Lock-4 vendor-key uniqueness guard
-- at the projection layer. The Model aggregate decider does NOT
-- enforce vendor-key uniqueness (define_model only checks stream
-- non-existence + cross-BC Family resolution), so two parallel
-- define_model calls with the same (manufacturer_name, part_number)
-- but a fresh model_id each would: (a) successfully append events
-- to two new streams, then (b) the projection INSERT for the second
-- stream would blow up with UniqueViolation, poisoning the bookmark
-- and diverging aggregate state from projection state.
--
-- Resolution: drop the projection-side uniqueness constraint, match
-- CORA's eventual-consistency convention (Family.name, Method.name,
-- Plan.name, Practice.name, Capability.code all lack uniqueness
-- checks at the projection tier; Capability cleared the exact same
-- shape in migration 20260518210000). Vendor-key uniqueness becomes
-- decider-tier operator-curation discipline at v1, enforced via a
-- list-by-vendor-key projection only if a real collision surfaces
-- during pilot operation.
--
-- The composite `(manufacturer_name, part_number)` columns stay on
-- the table for the manufacturer-keyed lookup path (audit + future
-- list-by-vendor-key read slice). Re-created as a non-unique index
-- so equality + prefix scans on the pair stay cheap; matches the
-- Capability precedent of "keep the column queryable, drop only the
-- UNIQUE constraint."
--
-- Forward-only cleanup follow-up to the original Model summary
-- migration; the table + columns + bookmark stay. Standard DROP +
-- CREATE; allowed-data-preserving.

-- atlas:safety:allow=drop-index-allowed-data-preserving

DROP INDEX IF EXISTS proj_equipment_model_summary_vendor_key_idx;

CREATE INDEX IF NOT EXISTS proj_equipment_model_summary_vendor_key_idx
    ON proj_equipment_model_summary (manufacturer_name, part_number);

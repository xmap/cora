-- Widen proj_equipment_asset_summary with the Asset.alternate_identifiers
-- facet: the additional human-/operator-facing identifiers (serial
-- numbers, inventory numbers, free-form Other tags) that travel
-- alongside the system-issued Asset.id without replacing it.
--
-- Additive JSONB array per Lock A + Lock G of
-- project_asset_alternate_identifiers_design. Stored as a sorted list
-- of `{"kind": str, "value": str}` objects (sorted by (kind, value)
-- at write time for byte-stable replay). Legacy AssetRegistered events
-- written before the slice ships fold to an empty array via the
-- NOT NULL DEFAULT '[]'::jsonb shape.
--
-- ## Partial GIN index
--
-- The "find Asset by serial number" lookup hits the column with a
-- JSONB containment predicate (`alternate_identifiers @> '[{"kind":
-- "SerialNumber", "value": "..."}]'::jsonb`). GIN supports that
-- operator natively. Most Assets carry zero alternate identifiers in
-- v1 (PIDINST-compliant but operator-driven uptake takes time);
-- exclude the empty-array rows from the index to keep it tight, per
-- the parent_id partial-index precedent at
-- 20260512280000_init_proj_equipment_asset_summary.sql:54-56 and the
-- model_id partial-index precedent at
-- 20260602110000_add_asset_summary_model.sql.
--
-- ## Forward-only
--
-- Pure ADD COLUMN with safe default; greenfield-friendly; no backfill
-- needed. Rollback via a NEW compensating migration per
-- project_forward_only_migrations.
--
-- ## v1 scope reminders (see design memo Lock F)
--
-- No cross-Asset uniqueness check on (kind, value) at the DB layer;
-- collisions are operationally meaningful (two specimens shipped with
-- the same factory serial number is a vendor problem worth surfacing,
-- not a domain invariant to enforce). Future v2 may add a partial
-- unique index gated by an explicit unique-per-facility decision.

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN alternate_identifiers JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX proj_equipment_asset_summary_alternate_idx
    ON proj_equipment_asset_summary
    USING GIN (alternate_identifiers)
    WHERE jsonb_array_length(alternate_identifiers) > 0;

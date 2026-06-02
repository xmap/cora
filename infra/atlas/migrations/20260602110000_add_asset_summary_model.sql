-- Widen proj_equipment_asset_summary with the Asset.model_id facet:
-- the optional Model binding captured at registration that connects
-- a deployed Asset back to its catalog entry in the Model BC.
--
-- Additive nullable per Lock F of project_asset_model_binding_design.
-- No NOT NULL, no DEFAULT, no CHECK: legacy AssetRegistered events
-- written before the binding slice ships fold to model_id=None and
-- the projection writes NULL into the new column for those rows on
-- rebuild. Greenfield-friendly; no backfill needed.
--
-- ## Partial index
--
-- Mirrors the parent_id partial-index precedent at
-- 20260512280000_init_proj_equipment_asset_summary.sql:54-56. The
-- future "list Assets bound to Model X" lookup hits WHERE model_id
-- = $1; rows with model_id IS NULL never match that predicate and
-- are excluded from the index to keep it tight.
--
-- ## Forward-only
--
-- Pure ADD COLUMN; greenfield-friendly; no backfill needed. Rollback
-- via a NEW compensating migration per project_forward_only_migrations.

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN model_id UUID;

CREATE INDEX proj_equipment_asset_summary_model_idx
    ON proj_equipment_asset_summary (model_id)
    WHERE model_id IS NOT NULL;

-- Widen proj_equipment_asset_summary with the lifecycle date columns
-- needed by the PIDINST read-route assembler (commissioned_at +
-- decommissioned_at, PIDINST v1.0 Property 11) and reserve the
-- persistent_id JSONB column that slice F's assign_persistent_id
-- write path will populate (PIDINST v1.0 Property 1 DOI/Handle).
--
-- Per L2 + L3 + L4 of project_asset_persistent_id_design (slice E.1):
--
--   - commissioned_at is folded from AssetRegistered.occurred_at by the
--     extended AssetSummaryProjection.
--   - decommissioned_at is folded from AssetDecommissioned.occurred_at
--     by the extended AssetSummaryProjection.
--   - persistent_id is reserved nullable JSONB; ALWAYS NULL in E.1.
--     Slice F's assign_persistent_id mutation writes it.
--
-- ## Why one migration for three columns
--
-- All three columns belong to the same read-model widening for the
-- PIDINST integration. Splitting into three sibling migrations would
-- triple the per-migration h1 cascade overhead for no operational
-- benefit; the columns ship together and the projection extension
-- writes them together (commissioned_at on AssetRegistered,
-- decommissioned_at on AssetDecommissioned, persistent_id NEVER in
-- E.1). Trio-as-one-migration matches the existing
-- `add_asset_summary_drawing` precedent (drawing_system +
-- drawing_number + drawing_revision in one ALTER).
--
-- ## Forward-only
--
-- Pure ADD COLUMN with safe NULL defaults; greenfield-friendly; no
-- backfill needed (projections rebuild from the event store and pick
-- up the lifecycle timestamps on AssetRegistered / AssetDecommissioned
-- replay). Rollback via a NEW compensating migration per
-- project_forward_only_migrations.
--
-- ## v1 scope reminders (see design memo Lock 10 + Lock 21)
--
-- No index on persistent_id in E.1 (D13 deferred to slice F). The
-- bulk-mint operator UX will want `WHERE persistent_id IS NULL` over
-- this column; trigger the index when bulk-mint queries on a >10k-asset
-- facility exceed 1s. No index on commissioned_at / decommissioned_at
-- either; the PIDINST route reads them per-asset by primary key.

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN commissioned_at TIMESTAMPTZ NULL,
    ADD COLUMN decommissioned_at TIMESTAMPTZ NULL,
    ADD COLUMN persistent_id JSONB NULL DEFAULT NULL;

-- Rename `AssetLevel` value `Assembly` -> `Component` on the asset
-- summary projection.
--
-- The token `Assembly` is being freed for the new Assembly aggregate
-- (Equipment BC's 5th aggregate, designed in
-- [[project_assembly_aggregate_design]]). `Component` is the
-- replacement value at the ISA-88 Equipment-Module tier; `Unit` (the
-- tier above) stays untouched. The other five `AssetLevel` values
-- (Enterprise, Site, Area, Unit, Device) are unchanged.
--
-- Forward-only per [[project_forward_only_migrations]]. The
-- compensating rollback, if ever needed, is a new ADD migration that
-- reverses the value, not a DOWN step.
--
-- ## Operation order
--
-- 1. DROP the old CHECK so the backfill UPDATE can write 'Component'.
-- 2. UPDATE every 'Assembly' row to 'Component'.
-- 3. ADD the new CHECK with the renamed value set.
--
-- The table is briefly unconstrained between steps 1 and 3; that
-- window is single-transaction-bounded (Atlas wraps each migration
-- file in a transaction) so no other writer can observe the gap.
--
-- ## Greenfield posture
--
-- Zero rows live in `proj_equipment_asset_summary` with
-- level='Assembly' on any environment beyond test fixtures, so the
-- UPDATE is effectively a no-op in production. The migration still
-- ships the UPDATE so replay against any prior dev database that did
-- register such rows folds cleanly. The corresponding
-- `from_stored` wrap on the Asset evolver is intentionally NOT
-- added: under greenfield posture (lock at 66db6a1f8) we string-
-- replace events at rest if any ever surface, not at read time.

ALTER TABLE proj_equipment_asset_summary
    DROP CONSTRAINT proj_equipment_asset_summary_level_check;

UPDATE proj_equipment_asset_summary
    SET level = 'Component'
    WHERE level = 'Assembly';

ALTER TABLE proj_equipment_asset_summary
    ADD CONSTRAINT proj_equipment_asset_summary_level_check
        CHECK (level IN (
            'Enterprise',
            'Site',
            'Area',
            'Unit',
            'Component',
            'Device'
        ));

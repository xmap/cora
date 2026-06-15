-- Drop the legacy presents_as_family_id column (and its back-lookup
-- index) from the Assembly summary projection. The presenter-Family
-- path is retired: an Assembly now advertises global Role contracts via
-- presents_as (already a column on this table), so the scalar Family
-- pointer is dead weight. Forward-only; pre-pilot, no rows depend on it.

DROP INDEX IF EXISTS proj_equipment_assembly_summary_presents_as_family_id_idx;

ALTER TABLE proj_equipment_assembly_summary
    DROP COLUMN presents_as_family_id;

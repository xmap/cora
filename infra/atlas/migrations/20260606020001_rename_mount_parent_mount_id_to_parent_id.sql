-- Rename Mount projection columns `parent_mount_id` -> `parent_id`
-- in step with the aggregate-field rename of `Mount.parent_mount_id`
-- -> `Mount.parent_id`. The shorter form drops the redundant `_mount`
-- middle word now that the column lives on Mount-keyed tables; the
-- new payload key matches.
--
-- Forward-only per project_forward_only_migrations.md. Pre-pilot, so
-- the columns hold effectively zero rows; the rename is cheap.
--
-- ## Two tables touched
--
-- 1. `proj_equipment_mount_summary` carries `parent_mount_id UUID NULL`
--    plus a partial index `proj_equipment_mount_summary_parent_idx
--    ON ... (parent_mount_id) WHERE parent_mount_id IS NOT NULL`.
--    PostgreSQL `RENAME COLUMN` automatically follows the column into
--    the index definition (including the partial WHERE clause), so no
--    DROP / CREATE INDEX dance is required.
--
-- 2. `proj_equipment_mount_children` carries `parent_mount_id UUID
--    NOT NULL` as half of `PRIMARY KEY (parent_mount_id, child_mount_id)`.
--    PG's `RENAME COLUMN` likewise rewrites the PK definition in place.
--
-- `child_mount_id` stays as-is on the children table: it is a sibling
-- disambiguator independent of the aggregate field's name.

ALTER TABLE proj_equipment_mount_summary
    RENAME COLUMN parent_mount_id TO parent_id;

ALTER TABLE proj_equipment_mount_children
    RENAME COLUMN parent_mount_id TO parent_id;

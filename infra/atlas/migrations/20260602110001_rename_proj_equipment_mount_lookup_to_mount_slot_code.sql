-- Rename the mount projection from `mount_lookup` (the only `_lookup`
-- suffix in the projection corpus) to `mount_slot_code`, bringing it
-- in line with the `proj_<bc>_<base>_<rowtype>` convention every
-- sibling projection already follows. Per-row noun was the slot-code
-- mapping; the rename makes that explicit and removes the lone
-- outlier from the projection-table naming sweep.
--
-- Before: proj_equipment_mount_lookup
-- After:  proj_equipment_mount_slot_code
--
-- The bookmark name in `projection_bookmarks` is also renamed so the
-- projection class's `name` attribute matches; without that the
-- worker would re-fold the entire Mount history on first run after
-- the rename (writing duplicate rows that ON CONFLICT DO NOTHING
-- would absorb, but the bookmark drift would persist).
--
-- Forward-only: simple ALTER RENAME for table, index, and bookmark
-- row. No data movement, no downtime. Mirrors the
-- `asset_families -> asset_family_membership` precedent
-- (20260528100000).

ALTER TABLE proj_equipment_mount_lookup
    RENAME TO proj_equipment_mount_slot_code;

ALTER INDEX proj_equipment_mount_lookup_by_mount_idx
    RENAME TO proj_equipment_mount_slot_code_by_mount_idx;

UPDATE projection_bookmarks
    SET name = 'proj_equipment_mount_slot_code'
    WHERE name = 'proj_equipment_mount_lookup';

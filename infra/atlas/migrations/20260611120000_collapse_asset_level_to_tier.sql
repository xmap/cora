-- Collapse `AssetLevel` into `AssetTier`: rename the asset summary
-- projection column `level` -> `tier` and tighten its CHECK to the
-- three operational tiers {Unit, Component, Device}.
--
-- The upper three former AssetLevel values (Enterprise / Site / Area)
-- modeled facility-envelope scope, which is now owned by the Federation
-- `Facility` aggregate (FacilityKind{Site, Area}) and bound on an Asset
-- via `facility_code`. A root Asset is facility-anchored
-- (parent_id=None + facility_code set); its sub-Assets nest via
-- parent_id. The earlier soft-deprecation (Slice 8B fitness guard +
-- deferred drop) is replaced by this hard cutover; greenfield posture
-- makes the deferral unnecessary and the half-state confusing.
--
-- Forward-only per [[project_forward_only_migrations]]. The
-- compensating rollback, if ever needed, is a new ADD migration that
-- reverses the rename, not a DOWN step.
--
-- ## Operation order
--
-- 1. DROP the old `level` CHECK so the column can be renamed cleanly.
-- 2. RENAME COLUMN level -> tier (data preserved; no upcaster needed
--    because the lower-tier string values are identical).
-- 3. DELETE any rows whose tier is a retired upper value. Under
--    greenfield posture (no production rows) this is a no-op in
--    practice; it keeps replay against a prior dev database that
--    registered Enterprise/Site/Area assets from violating step 4.
--    Those rows represented facility-envelope assets that now belong
--    to the Facility aggregate, not the Asset hierarchy.
-- 4. ADD the new `tier` CHECK with the three-value set.
--
-- The table is briefly unconstrained between steps 1 and 4; that
-- window is single-transaction-bounded (Atlas wraps each migration
-- file in a transaction) so no other writer can observe the gap. No
-- index references `level` (only the keyset + parent_id indexes
-- exist), so nothing else needs renaming.

ALTER TABLE proj_equipment_asset_summary
    DROP CONSTRAINT proj_equipment_asset_summary_level_check;

ALTER TABLE proj_equipment_asset_summary
    RENAME COLUMN level TO tier;

DELETE FROM proj_equipment_asset_summary
    WHERE tier NOT IN ('Unit', 'Component', 'Device');

ALTER TABLE proj_equipment_asset_summary
    ADD CONSTRAINT proj_equipment_asset_summary_tier_check
        CHECK (tier IN ('Unit', 'Component', 'Device'));

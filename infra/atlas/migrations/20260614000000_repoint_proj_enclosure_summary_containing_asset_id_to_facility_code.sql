-- Repoint the Enclosure summary projection from the Equipment Asset axis
-- to the Federation Facility axis, aligning with the cross-deployment
-- convergent slug convention shipped across Slices 6, 7, 8:
-- `containing_asset_id UUID NOT NULL` -> `facility_code TEXT NOT NULL`.
--
-- The Enclosure.facility_code aggregate field and the EnclosureRegistered
-- payload key were repointed in the same step. The aggregate-level field's
-- type also flipped from UUID (Asset row id) to FacilityCode (cross-
-- deployment slug), so the projection column type changes alongside the
-- name. The new value stores the bare FacilityCode slug ("aps", "maxiv",
-- etc.) per the Slice 8A precedent on proj_equipment_asset_summary and the
-- Clearance facility_asset_id -> facility_code rename.
--
-- The USING cast preserves any existing dev/test data: UUID values cast to
-- their canonical string form, which downstream code overwrites on the
-- next register_enclosure.
--
-- The address-tuple partial UNIQUE INDEX and the plain index both
-- referenced the old column. Postgres auto-rewrites index column refs on a
-- RENAME, but the index NAMES still encode `containing_asset` semantics, so
-- this migration drops and recreates them on `facility_code` to keep the
-- index identifiers honest about what they gate.
--
-- Forward-only per project_forward_only_migrations.md. Greenfield
-- (pre-pilot): the Enclosure BC has no production rows, so the rename +
-- type-flip + index swap window is at its narrowest.

ALTER TABLE proj_enclosure_summary
    ALTER COLUMN containing_asset_id TYPE TEXT USING containing_asset_id::text;

ALTER TABLE proj_enclosure_summary
    RENAME COLUMN containing_asset_id TO facility_code;

-- Drop the old address-tuple UNIQUE INDEX and the plain lookup index; both
-- were named for the containing-Asset axis they used to gate.
DROP INDEX IF EXISTS proj_enclosure_summary_address_uq;
DROP INDEX IF EXISTS proj_enclosure_summary_containing_asset_idx;

-- Address-tuple uniqueness: one Active enclosure per (facility_code, name);
-- decommissioned rows free the name for re-registration within the same
-- Facility.
CREATE UNIQUE INDEX proj_enclosure_summary_address_uq
    ON proj_enclosure_summary (facility_code, name)
    WHERE lifecycle = 'Active';

-- Cross-BC lookup: list Active enclosures within a given Facility.
CREATE INDEX proj_enclosure_summary_facility_code_idx
    ON proj_enclosure_summary (facility_code)
    WHERE lifecycle = 'Active';

COMMENT ON COLUMN proj_enclosure_summary.facility_code IS
    'Containing Facility (Site / Area) this Enclosure sits within, keyed on the cross-deployment convergent slug. Cross-stream existence is a projection-side concern; no FK constraint.';

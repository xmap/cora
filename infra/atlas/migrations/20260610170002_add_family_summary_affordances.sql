-- Add the affordances set to the Family summary projection.
--
-- Cross-BC consumers resolve an Asset to its Family affordances at
-- command time via the AssetLookup port. The port's PostgresAssetLookup
-- adapter JOINs proj_equipment_asset_family_membership ->
-- proj_equipment_family_summary and aggregates the Families'
-- affordances into a single set. Until today the affordance set lived
-- only in the Family event stream; surfacing it on the projection lets
-- the lookup answer "which affordances does this Asset's Family
-- declare" without folding the Family stream.
--
-- The column mirrors proj_recipe_capability_summary.required_affordances
-- (TEXT[] of closed-enum Affordance value strings). FamilyDefined sets
-- it at genesis; FamilyVersioned replaces it (the versioned affordance
-- set is the new declaration); FamilyDeprecated leaves it untouched.
--
-- Backfill: existing rows default to the empty array. Replaying the
-- Family streams (or a targeted backfill) repopulates real values; an
-- empty array is a safe conservative default (an Asset whose Family
-- summary has not yet been repopulated simply fails the Capturing gate
-- until the projection catches up, which is the correct fail-closed
-- posture for a write-time business invariant).

ALTER TABLE proj_equipment_family_summary
    ADD COLUMN affordances TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[];

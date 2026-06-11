-- Equipment BC: add presents_as column to Family summary projection
-- (Layer 3 sub-slice 3B of [[project-role-aggregate-design]]).
--
-- Folds the new FamilyPresentsAsAdded / FamilyPresentsAsRemoved
-- events into the existing `proj_equipment_family_summary` read
-- model used by Layer-3 cross-aggregate satisfaction checks
-- (specifically 3D's `bind_plan_role` handler via the
-- `FamilyLookup` port shipped in 3B).
--
-- ## What this migration does
--
-- Adds `presents_as UUID[] NOT NULL DEFAULT ARRAY[]::UUID[]` so
-- existing Family rows default to the empty set and start receiving
-- role advertisements from the day 3B lands. Mirrors the
-- `required_affordances TEXT[]` column already present on the
-- table from its `proj_recipe_capability_summary` heritage.
--
-- The projection writer is extended in the same slice to:
--   - Refresh `affordances` (TEXT[]) on FamilyDefined +
--     FamilyVersioned (Family.affordances replaces wholesale on
--     version per the 5j semantics).
--   - Append role_id on FamilyPresentsAsAdded.
--   - Remove role_id on FamilyPresentsAsRemoved.
--
-- Pre-pilot: zero registered Family rows carry presents_as data
-- today; the column simply lights up as 3B / 3C / 3D / pilot
-- scenario seeds start using it. A projection replay-from-zero
-- (bookmark reset) repopulates `affordances` on existing
-- pre-3B-defined Family rows from their FamilyDefined event
-- payloads.
--
-- ## Mutable read model
--
-- cora_app already has full DML on the table; no GRANT changes
-- needed.

ALTER TABLE proj_equipment_family_summary
    ADD COLUMN presents_as UUID[] NOT NULL DEFAULT ARRAY[]::UUID[];

COMMENT ON COLUMN proj_equipment_family_summary.presents_as IS
    'Set of global Role contract ids this Family advertises (Layer 3 sub-slice 3B). Mutated incrementally via add_family_presents_as / remove_family_presents_as.';

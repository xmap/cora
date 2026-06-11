-- Equipment BC: add presents_as column to Assembly summary projection
-- (Layer 3 sub-slice 3C of [[project-role-aggregate-design]]).
--
-- Mirror of 3B's add_proj_equipment_family_summary_presents_as
-- migration for the Assembly aggregate. Folds the new
-- AssemblyPresentsAsAdded / AssemblyPresentsAsRemoved events into
-- the existing `proj_equipment_assembly_summary` read model so the
-- MCTOptics-style composed Assemblies (and future composing
-- assemblies) can advertise Role contracts in parallel with the
-- scalar `presents_as_family_id`.
--
-- ## What this migration does
--
-- Adds `presents_as UUID[] NOT NULL DEFAULT ARRAY[]::UUID[]` so
-- existing Assembly rows default to the empty set. The scalar
-- `presents_as_family_id` is RETAINED (per memo anti-hook #6: one
-- migration cycle); deprecation lands in a follow-up post-pilot
-- slice once 3D's bind_plan_role demonstrates the new path covers
-- the same operator-authoring needs.
--
-- The projection writer (assembly_summary.py) is extended in the
-- same slice to populate the column on AssemblyPresentsAsAdded /
-- AssemblyPresentsAsRemoved.
--
-- Pre-pilot: zero registered Assembly rows carry presents_as data
-- today; the column simply lights up as 3C / pilot scenario seeds
-- start using it.

ALTER TABLE proj_equipment_assembly_summary
    ADD COLUMN presents_as UUID[] NOT NULL DEFAULT ARRAY[]::UUID[];

COMMENT ON COLUMN proj_equipment_assembly_summary.presents_as IS
    'Set of global Role contract ids this Assembly advertises (Layer 3 sub-slice 3C). Mutated incrementally via add_assembly_presents_as / remove_assembly_presents_as. Parallel to the scalar presents_as_family_id retained per anti-hook #6 for one migration cycle.';

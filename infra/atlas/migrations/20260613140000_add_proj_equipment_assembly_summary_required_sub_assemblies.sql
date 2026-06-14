-- Equipment BC: add required_sub_assemblies column to the Assembly
-- summary projection.
--
-- Mirror of the add_proj_equipment_assembly_summary_presents_as
-- migration: adds the read-model column for the new
-- `required_sub_assemblies` event field so the assembly summary
-- captures the full structural subset (a parent Assembly composed of
-- version-pinned child links). The column complements content_hash:
-- content_hash answers "is this the same blueprint",
-- required_sub_assemblies answers "what child blueprints does it pin".
-- The column name matches the event field, mirroring the presents_as
-- field-to-column convention.
--
-- Each element is {slot_name, sub_assembly_id, content_hash}, the same
-- shape the AssemblyDefined / AssemblyVersioned event payloads carry.
-- The projection writer (assembly_summary.py) populates it on INSERT
-- (AssemblyDefined) and UPDATE (AssemblyVersioned).
--
-- Pre-pilot: zero registered Assembly rows carry sub-assembly links
-- today; existing rows default to the empty array.

ALTER TABLE proj_equipment_assembly_summary
    ADD COLUMN required_sub_assemblies JSONB NOT NULL DEFAULT '[]'::jsonb;

COMMENT ON COLUMN proj_equipment_assembly_summary.required_sub_assemblies IS
    'Version-pinned child Assembly links composing this Assembly. JSONB array of {slot_name, sub_assembly_id, content_hash}, mirroring the required_sub_assemblies event field. Each link pins the child content_hash at authoring time (snapshot).';

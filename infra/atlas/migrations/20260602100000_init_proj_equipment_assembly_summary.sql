-- Equipment BC's Assembly aggregate summary projection.
--
-- Folds the Assembly aggregate's lifecycle events into a queryable
-- read model. Used by the future `list_assemblies` and
-- `get_assembly` slices for the keyset-paginated list endpoint with
-- optional `status` / `content_hash` filters.
--
-- v1 subscribes to AssemblyDefined only; the AssemblyVersioned and
-- AssemblyDeprecated arms land with their respective slices per the
-- slice-per-commit discipline.
--
-- Subscribed events (v1):
--   - AssemblyDefined     -> INSERT (status=Defined, version from
--                             payload, content_hash from payload)
--   - AssemblyVersioned   -> UPDATE status=Versioned + version +
--                             content_hash (added with the slice)
--   - AssemblyDeprecated  -> UPDATE status=Deprecated (added with
--                             the slice)
--
-- `content_hash` is indexed for the future
-- "find Assemblies with this structural fingerprint" cross-facility
-- federation query (per project_federation_port_design). The
-- composite (created_at, assembly_id) index supports keyset
-- pagination on the list endpoint.
--
-- Mutable read model. cora_app gets full DML.
-- proj_equipment_assembly_summary matches:
--   - the table name (here)
--   - the bookmark row (INSERT below)
--   - `AssemblySummaryProjection.name` in
--     cora.equipment.projections.assembly_summary.

CREATE TABLE proj_equipment_assembly_summary (
    assembly_id           UUID        PRIMARY KEY,
    name                  TEXT        NOT NULL,
    presents_as_family_id UUID        NOT NULL,
    status                TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version               TEXT,
    content_hash          TEXT,
    created_at            TIMESTAMPTZ NOT NULL,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proj_equipment_assembly_summary_keyset_idx
    ON proj_equipment_assembly_summary (created_at, assembly_id);

-- Federation / dedup query support: find Assemblies by their
-- structural fingerprint. Partial index excludes NULL so the
-- empty-hash rows (pre-content_hash legacy events, none today)
-- do not occupy the index.
CREATE INDEX proj_equipment_assembly_summary_content_hash_idx
    ON proj_equipment_assembly_summary (content_hash)
    WHERE content_hash IS NOT NULL;

-- presents_as_family_id back-lookup: find every Assembly that
-- claims this Family identity. Used by Method.needed_families
-- satisfaction queries when an Assembly may stand in for the
-- declared Family.
CREATE INDEX proj_equipment_assembly_summary_presents_as_family_id_idx
    ON proj_equipment_assembly_summary (presents_as_family_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_assembly_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_assembly_summary')
ON CONFLICT DO NOTHING;

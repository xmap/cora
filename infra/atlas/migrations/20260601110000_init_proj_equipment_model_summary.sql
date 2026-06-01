-- Equipment BC projection: model summary.
--
-- Folds the Model aggregate's lifecycle events into the
-- `proj_equipment_model_summary` read model used by the future
-- `list_models` slice for `GET /models` keyset-paginated list
-- endpoint and by the vendor-key uniqueness guard at command time.
--
-- Subscribed events:
--   - ModelDefined       -> INSERT (status=Defined, version_tag preserved
--                          from payload when present, declared_families
--                          materialized from payload array)
--   - ModelVersioned     -> UPDATE status=Versioned, replaces
--                          name / manufacturer_* / part_number /
--                          declared_families / version_tag wholesale
--                          (a new revision restates the full identity
--                          block of the Model)
--   - ModelDeprecated    -> UPDATE status=Deprecated, sets
--                          deprecation_reason; vendor-key columns
--                          (manufacturer_name, part_number) preserved
--                          so the audit trail of "what was deprecated"
--                          stays answerable from the projection
--   - ModelFamilyAdded   -> UPDATE declared_families (append family_id,
--                          re-sorted to match the canonical event-
--                          payload ordering)
--   - ModelFamilyRemoved -> UPDATE declared_families (remove family_id)
--
-- `version_tag` is nullable because a freshly Defined Model may carry
-- no version label yet; ModelVersioned sets it on later revisions.
-- `deprecation_reason` is nullable for the same reason: only set when
-- ModelDeprecated fires.
--
-- `manufacturer_identifier` + `manufacturer_identifier_type` are both
-- nullable and travel together. The CHECK constraint enforces that
-- when an identifier is present the type is one of the closed set
-- (ROR, GRID, ISNI) and the two columns are both-set-or-both-null
-- (the value-object invariant lifted from the aggregate).
--
-- `declared_families` is JSONB rather than a join table because the
-- payload-as-stored shape is an array of family-id strings sorted
-- canonically, and the read slice returns it verbatim. A future
-- `proj_equipment_model_families` join projection would be added if
-- a list-models-by-family use case lands.
--
-- The UNIQUE (manufacturer_name, part_number) index is the Lock-4
-- vendor-key uniqueness guard from the design memo: two Models from
-- the same manufacturer cannot share a part number. Indexed for both
-- the constraint and for the manufacturer-keyed lookup path.
--
-- Mutable read model. cora_app gets full DML.
-- proj_equipment_model_summary matches:
--   - the table name (here)
--   - the bookmark row (INSERT below)
--   - `ModelSummaryProjection.name` in cora.equipment.projections.model.

CREATE TABLE proj_equipment_model_summary (
    model_id                       UUID        PRIMARY KEY,
    name                           TEXT        NOT NULL,
    manufacturer_name              TEXT        NOT NULL,
    manufacturer_identifier        TEXT,
    manufacturer_identifier_type   TEXT,
    part_number                    TEXT        NOT NULL,
    declared_families              JSONB       NOT NULL,
    status                         TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Versioned', 'Deprecated')
    ),
    version_tag                    TEXT,
    deprecation_reason             TEXT,
    created_at                     TIMESTAMPTZ NOT NULL,
    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT proj_equipment_model_summary_identifier_type_chk CHECK (
        manufacturer_identifier_type IS NULL
        OR manufacturer_identifier_type IN ('ROR', 'GRID', 'ISNI')
    ),
    CONSTRAINT proj_equipment_model_summary_identifier_paired_chk CHECK (
        (manufacturer_identifier IS NULL
            AND manufacturer_identifier_type IS NULL)
        OR (manufacturer_identifier IS NOT NULL
            AND manufacturer_identifier_type IS NOT NULL)
    )
);

-- Lock-4 vendor-key uniqueness: a manufacturer can publish at most
-- one Model under a given part number.
CREATE UNIQUE INDEX proj_equipment_model_summary_vendor_key_idx
    ON proj_equipment_model_summary (manufacturer_name, part_number);

CREATE INDEX proj_equipment_model_summary_keyset_idx
    ON proj_equipment_model_summary (created_at, model_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_model_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_model_summary')
ON CONFLICT DO NOTHING;

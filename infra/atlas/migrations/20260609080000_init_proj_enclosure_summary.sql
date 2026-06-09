-- Enclosure BC: Enclosure summary read model.
--
-- Folds the Enclosure aggregate's lifecycle events into the
-- `proj_enclosure_summary` read model used by future list / get
-- slices and by the pre-flight gate query that
-- start_procedure / start_run consult before transitioning.
--
-- Subscribed events (apply order):
--   - EnclosureRegistered      -> INSERT (lifecycle='Active',
--                                         permit_status='Unknown',
--                                         registered_at=occurred_at)
--   - EnclosurePermitObserved  -> UPDATE permit_status,
--                                        last_observed_at,
--                                        last_observed_reason,
--                                        last_trigger,
--                                        last_source_kind,
--                                        last_source_id
--   - EnclosureDecommissioned  -> UPDATE lifecycle='Decommissioned',
--                                        decommissioned_at,
--                                        decommissioned_by
--
-- Address tuple per L-proj-1: one row per enclosure_id; the
-- `(containing_asset_id, name)` tuple is PARTIAL UNIQUE on
-- lifecycle='Active' so a decommissioned name is freed for
-- re-registration on the same Asset. Mirrors the Supply
-- collapse-to-Asset address pattern, not Facility's full-table
-- code uniqueness.
--
-- Envelope columns per L-proj-2: last_observed_at /
-- last_observed_reason / last_trigger / last_source_kind /
-- last_source_id are denormalized to the projection only; the
-- aggregate state stays slim. The `monitor_ref` payload string
-- splits to last_source_kind + last_source_id at projection
-- write so consumers query `WHERE last_source_kind = 'EpicsPv'`
-- without LIKE-substring fragility.
--
-- CHECK constraints close the full enum sets day-one
-- (lifecycle, permit_status, last_trigger) so future transition
-- slices land without constraint migration. The column is
-- forward-compatible across the full Operator / Monitor / Auto
-- trigger union.
--
-- No cross-projection FK constraints to Asset; cross-stream
-- containing_asset_id existence is a projection-side concern.

CREATE TABLE proj_enclosure_summary (
    enclosure_id            UUID         PRIMARY KEY,
    name                    TEXT         NOT NULL CHECK (length(name) > 0),
    containing_asset_id     UUID         NOT NULL,
    lifecycle               TEXT         NOT NULL CHECK (
        lifecycle IN ('Active', 'Decommissioned')
    ),
    permit_status           TEXT         NOT NULL CHECK (
        permit_status IN ('Unknown', 'Permitted', 'NotPermitted')
    ),
    registered_at           TIMESTAMPTZ  NOT NULL,
    registered_by           UUID         NOT NULL,
    last_observed_at        TIMESTAMPTZ,
    last_observed_reason    TEXT,
    last_trigger            TEXT         CHECK (
        last_trigger IS NULL OR last_trigger IN ('Operator', 'Monitor', 'Auto')
    ),
    last_source_kind        TEXT,
    last_source_id          TEXT,
    decommissioned_at       TIMESTAMPTZ,
    decommissioned_by       UUID,
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE proj_enclosure_summary IS
    'Enclosure summary read model. Lifecycle {Active, Decommissioned} terminal FSM; permit_status {Unknown, Permitted, NotPermitted}; address tuple (containing_asset_id, name) PARTIAL UNIQUE on lifecycle=Active.';
COMMENT ON COLUMN proj_enclosure_summary.containing_asset_id IS
    'Asset that physically contains this Enclosure. Cross-stream existence is a projection-side concern; no FK constraint.';
COMMENT ON COLUMN proj_enclosure_summary.last_source_kind IS
    'Split of the EnclosurePermitObserved monitor_ref payload string. NULL until first observation; populated by Monitor/Auto triggers (for example EpicsPv) or left NULL for Operator-triggered observations.';
COMMENT ON COLUMN proj_enclosure_summary.last_source_id IS
    'Identifier portion of the split monitor_ref. Paired with last_source_kind so consumers query WHERE last_source_kind = X without LIKE-substring fragility.';

-- Address-tuple uniqueness: one Active enclosure per
-- (containing_asset_id, name); decommissioned rows free the
-- name for re-registration on the same Asset.
CREATE UNIQUE INDEX proj_enclosure_summary_address_uq
    ON proj_enclosure_summary (containing_asset_id, name)
    WHERE lifecycle = 'Active';

-- Cross-BC lookup: list Active enclosures contained by a given
-- Asset for future binding slices.
CREATE INDEX proj_enclosure_summary_containing_asset_idx
    ON proj_enclosure_summary (containing_asset_id)
    WHERE lifecycle = 'Active';

-- Pre-flight gate: start_procedure / start_run filter
-- enclosures by (lifecycle, permit_status) before transitioning.
CREATE INDEX proj_enclosure_summary_gate_idx
    ON proj_enclosure_summary (lifecycle, permit_status);

-- Mutable read model. cora_app gets full CRUD; the projection
-- writer needs INSERT + UPDATE, and projection rebuilds need
-- TRUNCATE / DELETE.
GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_enclosure_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_enclosure_summary')
ON CONFLICT DO NOTHING;

-- Data BC's second projection: acquisition summary.
--
-- Folds the Acquisition aggregate's single AcquisitionRecorded event
-- into the `proj_data_acquisition_summary` read model. The Acquisition
-- is a recorded-fact-chain: terminal at genesis, one stream per
-- Acquisition, exactly one event ever. The projection mirrors the
-- birth-certificate fact that a producing Asset captured bytes into a
-- Dataset under an optional Run context.
--
-- Subscribed events:
--   - AcquisitionRecorded -> INSERT (status='Recorded')
--
-- Dual-time columns:
--   - captured_at: instrument wall-clock (caller-asserted provenance)
--   - recorded_at: CORA-side wall-clock when record_acquisition ran
--     (the event's occurred_at payload key)
--
-- The carrier dicts (settings, evidence) land as JSONB NOT NULL; both
-- may be the empty object `{}` but never NULL.
--
-- NO UNIQUE INDEX on (dataset_id, producing_asset_id, captured_at):
-- multiple Acquisitions per that tuple are legal (calibration replays,
-- partial re-acquisitions, paired flat-fields, rapid-fire detector
-- frames). Same-stream-id strictness is enforced at append time, not
-- by a projection constraint.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_data_acquisition_summary (
    acquisition_id     UUID        PRIMARY KEY,
    dataset_id         UUID        NOT NULL,
    producing_asset_id UUID        NOT NULL,
    producing_run_id   UUID,
    captured_at        TIMESTAMPTZ NOT NULL,
    settings           JSONB       NOT NULL,
    evidence           JSONB       NOT NULL,
    recorded_at        TIMESTAMPTZ NOT NULL,
    recorded_by        UUID        NOT NULL,
    status             TEXT        NOT NULL CHECK (
        status IN ('Recorded')
    ),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- "Acquisitions for Dataset X, newest capture first" is the dominant
-- read (lineage card, supersedence graph by capture time).
CREATE INDEX proj_data_acquisition_summary_dataset_idx
    ON proj_data_acquisition_summary (dataset_id, captured_at DESC);

-- "Acquisitions captured by Asset X, newest first" (per-instrument
-- capture history / cadence cardinality monitor).
CREATE INDEX proj_data_acquisition_summary_asset_idx
    ON proj_data_acquisition_summary (producing_asset_id, captured_at DESC);

-- "Acquisitions for Run X, newest first". Partial: standalone
-- captures (calibration / dark-field) have no Run context.
CREATE INDEX proj_data_acquisition_summary_run_idx
    ON proj_data_acquisition_summary (producing_run_id, captured_at DESC)
    WHERE producing_run_id IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_data_acquisition_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_data_acquisition_summary')
ON CONFLICT DO NOTHING;

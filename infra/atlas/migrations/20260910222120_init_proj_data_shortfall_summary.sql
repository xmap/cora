-- Data BC's newest projection: shortfall summary.
--
-- Folds the Shortfall aggregate's single ShortfallRecorded event into
-- the `proj_data_shortfall_summary` read model. The Shortfall is a
-- recorded-fact-chain: terminal at genesis, one stream per
-- capture_path_id, exactly one event ever. The projection mirrors the
-- fact that an observed capture can never become a Dataset, a
-- judgement made once as of the producing Run's terminal.
--
-- Subscribed events:
--   - ShortfallRecorded -> INSERT (status='Recorded')
--
-- Dual-time columns:
--   - file_modified_at / run_ended_at: the two sides of the finality
--     judgement, kept so the verdict stays checkable without going
--     back to the file (see cora.data.aggregates.shortfall.state's
--     module docstring).
--   - recorded_at: CORA-side wall-clock when the Shortfall was
--     recorded (the event's occurred_at payload key).
--
-- Frame accounting: projection_count is what the file actually holds;
-- commanded_projection_count is what the scan was told to collect and
-- is NULL when the file does not record it; dropped_frame_count is
-- the detector's own discard count, also NULL when absent and a
-- SEPARATE fact from the shortfall between the other two.
--
-- Personal data: host/root are the facility-level storage tier
-- (tomdet, /local1/2BM), never the path itself. capture_path_id is the
-- surrogate key of the run_capture_path vault row. Everything strictly
-- between the root and the filename never reaches this table.
--
-- NO CHECK on reason: ShortfallReason is closed at the aggregate tier
-- (a StrEnum) with a single member today; a DB-tier CHECK would need
-- editing in lockstep with every future member and buys little the
-- aggregate does not already guarantee.
--
-- UNIQUE INDEX on capture_path_id: one Shortfall per observation is
-- the aggregate's core invariant, mirroring ScanIngestCandidateLookup's
-- own per-location exclude key (scoped the same way, for the same
-- reason). Enforced here at the DB tier in addition to the
-- deterministic (uuid5) stream id.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_data_shortfall_summary (
    shortfall_id                UUID        PRIMARY KEY,
    producing_run_id            UUID        NOT NULL,
    capture_path_id             UUID        NOT NULL,
    host                        TEXT        NOT NULL,
    root                        TEXT        NOT NULL,
    projection_count            INTEGER     NOT NULL CHECK (projection_count >= 0),
    commanded_projection_count  INTEGER     CHECK (commanded_projection_count >= 0),
    dropped_frame_count         INTEGER     CHECK (dropped_frame_count >= 0),
    reason                      TEXT        NOT NULL,
    file_modified_at            TIMESTAMPTZ NOT NULL,
    run_ended_at                TIMESTAMPTZ NOT NULL,
    recorded_at                 TIMESTAMPTZ NOT NULL,
    recorded_by                 UUID        NOT NULL,
    status                      TEXT        NOT NULL CHECK (
        status IN ('Recorded')
    ),
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One Shortfall per observation is the aggregate's core invariant
-- (mirrors ScanIngestCandidateLookup's own exclude key). Enforced here
-- at the DB tier in addition to the deterministic (uuid5) stream id.
CREATE UNIQUE INDEX proj_data_shortfall_summary_capture_path_idx
    ON proj_data_shortfall_summary (capture_path_id);

-- "Shortfalls recorded against Run X, newest first" (per-run finality
-- review).
CREATE INDEX proj_data_shortfall_summary_run_idx
    ON proj_data_shortfall_summary (producing_run_id, recorded_at DESC);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_data_shortfall_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_data_shortfall_summary')
ON CONFLICT DO NOTHING;

-- Slice 13 (memory/project_witnessed_run_prelive_slices.md): PII vault
-- for a witnessed Run's observed capture file path.
--
-- 2-BM's directory layout embeds a surname and a proposal number
-- (tomoscan_2bm.py:474-477, `{ExperimentYearMonth}-{UserLastName}-
-- {ProposalNumber}`), so the full observed path is personal data by
-- construction. It must never land on an event (events are immutable
-- and INSERT-only at the role level, so PII written there could never
-- be erased). This table mirrors actor_profile (memory/project_pii_vault)
-- exactly: single mutable table, one row per Run, erasable by a future
-- slice via DELETE.
--
-- Naming: aggregate-prefixed (run_), not proj_-prefixed: this is a
-- mutable vault table, not a projection, same distinction actor_profile
-- draws from proj_access_actor_summary.
--
-- Schema decisions (mirroring actor_profile's init migration):
--   - run_id is both PK and (application-level) link to the Run
--     aggregate's stream_id. No SQL FK to events.stream_id because the
--     events table is INSERT-only at the role level per
--     project_immutability_guarantee; FK enforcement is application
--     discipline.
--   - observed_path CHECK upper bound is 511: the areaDetector file
--     plugin's FullFileName_RBV is a DBR_CHAR waveform with NELM=512
--     (confirmed against ADCore's NDFile.template), so a decoded string
--     of 511+ chars already reads as network-truncated at the
--     application layer and is never appended by RunWitnessRecorder;
--     this CHECK is defense-in-depth against that same fact, not the
--     primary guard.
--   - No forgotten_at / soft-delete column: it would itself be PII
--     ("this Run's capture path existed and was erased on Y").
--   - No UNIQUE constraint on observed_path: two Runs writing to the
--     same directory on the same day is realistic (multiple scans, one
--     proposal); UNIQUE under RLS also leaks via constraint-violation
--     timing, same reasoning as actor_profile.
--   - created_at is application-supplied (the promotion's own clock
--     read, matching the observation's dual-clock discipline elsewhere
--     in this feature). updated_at defaults to now() for a future
--     rename/rewrite path.
--
-- RLS posture (defense-in-depth on a mutable PII surface):
--   - ENABLE ROW LEVEL SECURITY: default-deny; the two CREATE POLICY
--     statements below grant the access cora_app needs.
--   - FORCE ROW LEVEL SECURITY: defense-in-depth against the
--     table-owner role bypassing policy.
--   - Two flat permissive policies for cora_app (read + write); both
--     USING (true) for v1, cora_app being the only runtime role.
--
-- No erasure slice ships in this commit (rule-of-three; nothing calls
-- DELETE yet), but DELETE is granted now so a future forget-style slice
-- needs no follow-up grant migration.

CREATE TABLE run_capture_path (
    run_id        UUID        PRIMARY KEY,
    observed_path TEXT        NOT NULL CHECK (length(observed_path) BETWEEN 1 AND 511),
    observed_at   TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE run_capture_path IS
    'PII vault for a witnessed Run''s observed capture file path (memory/project_witnessed_run_prelive_slices.md, slice 13). Mutable. No SQL FK to events (INSERT-only role); run_id matches the Run aggregate stream_id by application discipline.';
COMMENT ON COLUMN run_capture_path.run_id IS
    'Matches Run aggregate stream_id. One row per witnessed Run that has a resolved capture path.';
COMMENT ON COLUMN run_capture_path.observed_path IS
    'The full path read from the areaDetector file plugin''s FullFileName_RBV readback. Personal data (embeds a surname + proposal number at 2-BM): never referenced from an event payload, never logged in full.';
COMMENT ON COLUMN run_capture_path.observed_at IS
    'The substrate''s own timestamp for this reading (Measurement.produced_at), not CORA''s clock. Used at write time to prove the reading postdates the Run''s own BEGUN time.';

-- Mutable PII vault: cora_app gets full CRUD. DELETE is the future
-- erasure mechanism; UPDATE lets a later slice correct/rewrite a row.
GRANT SELECT, INSERT, UPDATE, DELETE ON run_capture_path TO cora_app;

-- Row-Level Security: defense-in-depth.
ALTER TABLE run_capture_path ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_capture_path FORCE  ROW LEVEL SECURITY;

CREATE POLICY run_capture_path_cora_app_read
    ON run_capture_path FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY run_capture_path_cora_app_write
    ON run_capture_path FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

-- Capture probe trail: append-only record of CORA's reach to the
-- capture-watch substrate, separate from the CaptureLifecycleObservation
-- phase claims a RunWitnessRecorder acts on.
--
-- See memory/project_witnessed_run_prelive_slices.md (slice 16) and
-- the shipped precedent this mirrors, entries_enclosure_permit_probes
-- (memory/project_enclosure_permit_probe_design.md). The 2-BM tomoscan
-- IOC was unreachable 2026-08-14 through at least 2026-08-16; the
-- deployed service wrote 7,031 `run_witness.capture_unreached` log
-- lines and zero database rows in that window. (That count is lower
-- than a naive continuous-outage x measured-cadence model below would
-- predict; not reconciled here -- possibly fewer configured PVs,
-- intermittent connectivity, or a process restart resetting counters.
-- Reported as the motivating fact, not verified against the volume
-- estimate.) This table is the mechanism that lets the record tell "no
-- scan ran" apart from "CORA was blind."
--
-- ## Two facts, two homes
--
-- The CaptureLifecycleObservation events a RunWitnessRecorder acts on
-- (by way of a promoted Run, when recording is on) answer what the
-- substrate said. This table answers whether CORA could reach it.
-- Neither substitutes for the other, and this table never carries the
-- observed phase.
--
-- ## Scoped by capture_code (TEXT), not a minted aggregate id
--
-- Every other entries table with no envelope (entries_run_feed_heartbeats,
-- entries_enclosure_permit_probes) scopes by a real aggregate's UUID
-- (run_id, enclosure_id). A capture code has no backing aggregate: it
-- is a bare deployment-declared string (Settings.capture_watch_pvs'
-- outer key), already CORA's identifier for a watched source elsewhere
-- (external_refs' Identifier(scheme="capture-code", ...), the baseline
-- and experiment-identity readers, every run_witness.capture_* log
-- line). Minting an aggregate purely to get a UUID would model the
-- TomoScan-orchestration concept CORA's own seam intends to dissolve,
-- on a rule-of-three count of one (memory/project_seam_model.md).
-- Reach is a property of the CHANNEL, which outlives every Run -- the
-- same reason run_id cannot work here: the trail must cover the gaps
-- BETWEEN Runs, when no run_id exists at all.
--
-- This is the first entries table scoped by a string rather than an
-- aggregate id. cora.infrastructure.record_export._registry's
-- EntriesReader type is widened (UUID | str) to accommodate it; see
-- that module's docstring for the export-reachability argument this
-- divergence required.
--
-- ## One row per (capture_code, PV), never per code
--
-- A capture code can pump several independently-subscribed PVs
-- (`status` required, `abort` optional per Settings.capture_watch_pvs);
-- each carries its own source_id. One row per observation per PV,
-- mirroring the permit probe's one-row-per-observation shape exactly.
--
-- ## reach_tier: two values shipped, mirroring the enclosure precedent
--
-- 'RELAYED' means CORA received or fetched a value through the
-- configured channel; 'UNREACHED' means it could not, this tick. A
-- stronger tier for a confirmed direct round trip to the authoritative
-- source is deliberately NOT defined yet, matching
-- entries_enclosure_permit_probes' own reasoning: no producer in this
-- codebase can currently prove one. The column is a length-CHECK, not
-- a value-enumerating CHECK, so a future value needs no migration.
--
-- ## phase_claimed, mirroring status_claimed
--
-- Whether the observation this probe accompanies also carried a
-- CaptureLifecycleObservation.phase claim (a real status push, or an
-- asserted `abort` reading) versus being probe-only or an
-- unreached/disconnected read (phase is None in both). A fact about
-- the PROBE, not the capture.
--
-- ## observed_at DIVERGES from the permit-probe precedent
--
-- entries_enclosure_permit_probes carries only recorded_at. That is NOT
-- because no producer timestamp crosses the EnclosureObserver port --
-- EnclosureObservation.observed_at exists and reaches the enclosure's
-- own transition event -- it is a scoping choice the permit-probe
-- design made for its own row shape. This table makes the different,
-- deliberate choice to carry CaptureLifecycleObservation.observed_at
-- (nullable: None for an unreached/probe-only read) on every row: the
-- observation already carries the field and it costs nothing extra.
--
-- ## Expected volume
--
-- Verified from source: the ~10s cadence measured in the 2026-08-14
-- outage's log lines is _run_witness.py's own _RECONNECT_DELAY_SECONDS
-- (5.0s) plus EpicsCaControlPort._DEFAULT_TIMEOUT_S (5.0s), the same
-- mechanism the enclosure gate review diagnosed for permit probes --
-- NOT capture_watch_probe_tick_seconds (defaults to None, disabling
-- polling entirely, and irrelevant even when set: _poll is recreated
-- fresh inside every _drain call and is cancelled within ~5s of a dead
-- reconnect, long before its first tick) and NOT
-- capture_progress_flush_tick_seconds (a numerically coincidental,
-- functionally unrelated 10.0s default). Roughly 8,640 x (the number of
-- PVs reaching observe_capture for a code) rows/day while fully
-- unreachable; fewer while push-driven and healthy. This scales with
-- configured roles (2-BM currently declares both status and abort:
-- two independent reach streams for its one code), not a single
-- constant.
--
-- ## Append-only INSERT, not UPSERT
--
-- One row per observation. No natural dedup key (event_id is a fresh
-- id per observation), so no ON CONFLICT, matching
-- entries_enclosure_permit_probes' own shape for the same reason
-- (UNLIKE entries_run_feed_heartbeats, which does use ON CONFLICT
-- DO NOTHING: a heartbeat's source_id is a natural per-feeder identity
-- worth deduplicating a retry against; a probe observation has none).

CREATE TABLE entries_run_capture_probes (
    event_id      uuid         PRIMARY KEY,
    capture_code  text         NOT NULL CHECK (length(capture_code) BETWEEN 1 AND 200),
    source_kind   text         NOT NULL CHECK (length(source_kind) BETWEEN 1 AND 50),
    source_id     text         NOT NULL CHECK (length(source_id) BETWEEN 1 AND 200),
    reach_tier    text         NOT NULL CHECK (length(reach_tier) BETWEEN 1 AND 32),
    phase_claimed boolean      NOT NULL,
    observed_at   timestamptz  NULL,
    recorded_at   timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON COLUMN entries_run_capture_probes.capture_code IS
    'Deployment-declared watch code (Settings.capture_watch_pvs outer key). No backing aggregate; see the migration header. The 1-200 bound has no independent precedent elsewhere (capture_code is a bare str on the command) and is borrowed from source_id''s own bound, the closest analog.';
COMMENT ON COLUMN entries_run_capture_probes.reach_tier IS
    'Stored value is ReachTier.value: ''Relayed'' or ''Unreached'' in v1 (NOT the all-caps member name). A stronger direct-round-trip tier is reserved and unused; see the migration header.';
COMMENT ON COLUMN entries_run_capture_probes.observed_at IS
    'The substrate''s own read time (CaptureLifecycleObservation.observed_at). NULL for a probe-only tick or an unreached/disconnected read.';

-- Supports the coverage read: latest probe per (capture_code, PV) via
-- MAX(recorded_at) / ORDER BY recorded_at DESC LIMIT 1; a per-code
-- rollup across every PV can still range-scan the leading column.
CREATE INDEX entries_run_capture_probes_capture_code_source_recorded_idx
    ON entries_run_capture_probes (capture_code, source_id, recorded_at DESC);

-- cora_app has no table-level default privileges in this database;
-- grant explicitly rather than repeating the false "inherits via ALTER
-- DEFAULT PRIVILEGES" claim several other entries_* migration headers
-- carry.
GRANT SELECT, INSERT ON entries_run_capture_probes TO cora_app;

-- Append-only at the role level (project_immutability_guarantee.md):
-- this removes mutation privileges so the append-only shape cannot be
-- silently broken.
REVOKE UPDATE, DELETE, TRUNCATE ON entries_run_capture_probes FROM cora_app; -- atlas:safety:allow=append-only revoke, not destructive DDL

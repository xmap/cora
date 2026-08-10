-- Permit probe trail: append-only record of CORA's reach to the
-- enclosure permit substrate, separate from the EnclosurePermitObserved
-- transition events.
--
-- See [[project_enclosure_permit_probe_design]]. The permit-status
-- projection advances only on a CHANGE (the decider is status-change-
-- only), so a stale value means "no transition since", never "not
-- observed since". This table is the mechanism that tells the two
-- apart: one row per observation the monitor's EnclosureObserver
-- surfaces, whether or not it caused a transition.
--
-- ## Two facts, two homes
--
-- `proj_enclosure_summary.permit_status` answers what the interlock
-- said; this table answers whether CORA could reach it. Neither
-- substitutes for the other. This table does NOT carry the observed
-- permit value, so it cannot become a second source of truth for
-- permit status.
--
-- ## reach_tier: two values shipped, a third reserved
--
-- 'RELAYED' means CORA received or fetched a value through the
-- configured channel; 'UNREACHED' means it could not, this tick.
-- Reach is not the same as belief: a Bad-quality reading is a RELAYED
-- probe with an unbelievable value, because reachability and
-- believability are different questions (permit_status answers the
-- second). A stronger tier for a confirmed direct round trip to the
-- authoritative source is deliberately NOT defined yet: no producer in
-- this codebase can currently prove one (2-BM reads through a caching
-- EPICS CA gateway), and shipping an unearned strong claim is worse
-- than shipping none. Adding a value later needs no migration, since
-- the column is a length-CHECK, not a value-enumerating CHECK.
--
-- `status_claimed` distinguishes, within a single reach_tier value,
-- whether the observation also carried a permit-status claim (a push
-- delivery, or a real substrate disconnect) versus being probe-only (a
-- periodic re-affirmation read that intentionally makes no status
-- claim). This is a fact about the PROBE, not the hutch, so recording
-- it does not create a second source of truth for permit status.
--
-- ## Append-only INSERT, not UPSERT
--
-- One row per observation. An UPSERT would need UPDATE, which the
-- append-only cora_app role is REVOKEd from (test_migration_revokes
-- enforces this for every entries_* table). Mirrors
-- entries_run_feed_heartbeats and the other entries_* tables.
--
-- ## recorded_at is the only anchor
--
-- No producer-asserted timestamp crosses the EnclosureObserver port
-- (see the port docstring), so this table carries only the DB write
-- time. Consumer-side queueing lag can forward-date a row relative to
-- when reach actually happened; there is no second timestamp to detect
-- this in v1.

CREATE TABLE entries_enclosure_permit_probes (
    event_id        uuid         PRIMARY KEY,
    enclosure_id    uuid         NOT NULL,
    source_kind     text         NOT NULL CHECK (length(source_kind) BETWEEN 1 AND 50),
    source_id       text         NOT NULL CHECK (length(source_id) BETWEEN 1 AND 200),
    reach_tier      text         NOT NULL CHECK (length(reach_tier) BETWEEN 1 AND 32),
    status_claimed  boolean      NOT NULL,
    recorded_at     timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON COLUMN entries_enclosure_permit_probes.reach_tier IS
    'RELAYED or UNREACHED in v1. A stronger direct-round-trip tier is reserved and unused; see the migration header.';

-- Supports the coverage read: latest probe per enclosure via
-- MAX(recorded_at) / ORDER BY recorded_at DESC LIMIT 1.
CREATE INDEX entries_enclosure_permit_probes_enclosure_recorded_idx
    ON entries_enclosure_permit_probes (enclosure_id, recorded_at DESC);

-- cora_app has no table-level default privileges in this database (only
-- ALTER DEFAULT PRIVILEGES ... ON SEQUENCES exists); grant explicitly
-- rather than repeating the false "inherits via ALTER DEFAULT
-- PRIVILEGES" claim several other entries_* migration headers carry.
GRANT SELECT, INSERT ON entries_enclosure_permit_probes TO cora_app;

-- Append-only at the role level (project_immutability_guarantee.md):
-- this removes mutation privileges so the append-only shape cannot be
-- silently broken.
REVOKE UPDATE, DELETE, TRUNCATE ON entries_enclosure_permit_probes FROM cora_app; -- atlas:safety:allow=append-only revoke, not destructive DDL

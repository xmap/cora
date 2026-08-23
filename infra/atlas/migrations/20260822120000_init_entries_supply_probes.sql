-- Supply probe trail: append-only record of CORA's reach to a Supply's
-- observation substrate (the BLEPS channels), separate from the
-- SupplyDegraded / SupplyMarkedUnavailable / SupplyMarkedRecovering
-- transition events.
--
-- Mirrors entries_enclosure_permit_probes exactly, one BC over: the
-- Supply BC's observer is the third instance of this pattern (Enclosure,
-- Run/capture, now Supply), so this migration reuses its shape rather
-- than inventing a new one. Without this table, a Supply that has read
-- clear for six hours is indistinguishable from a Supply CORA has not
-- looked at for six hours, which is exactly the ambiguity a status-
-- change-only observer decider (see observe_supply_status/decider.py)
-- otherwise leaves unresolved.
--
-- ## Two facts, two homes
--
-- `proj_supply_summary.status` answers what BLEPS reported; this table
-- answers whether CORA could reach it. Neither substitutes for the
-- other. This table does NOT carry the observed status, so it cannot
-- become a second source of truth for Supply status.
--
-- ## reach_tier: two values shipped, a third reserved
--
-- 'RELAYED' means CORA received or fetched a value through the
-- configured channel; 'UNREACHED' means it could not, this tick. Reach
-- is not the same as belief: a Good-quality-but-uninterpretable reading
-- (BLEPS-4, an unrecognized enum label) is still a RELAYED probe with
-- an unbelievable value, because reachability and believability are
-- different questions. A stronger tier for a confirmed direct round
-- trip to the authoritative source is deliberately NOT defined yet, for
-- the same reason the enclosure migration gives: no producer here can
-- currently prove one. Adding a value later needs no migration, since
-- the column is a length-CHECK, not a value-enumerating CHECK.
--
-- `status_claimed` distinguishes, within a single reach_tier value,
-- whether the observation also carried a status claim (the aggregated
-- BLEPS verdict resolved to tripped or clear) versus being probe-only
-- (a periodic re-affirmation that intentionally makes no status claim).
-- This is a fact about the PROBE, not the resource, so recording it
-- does not create a second source of truth for Supply status.
--
-- ## Append-only INSERT, not UPSERT
--
-- One row per observation. An UPSERT would need UPDATE, which the
-- append-only cora_app role is REVOKEd from (test_migration_revokes
-- enforces this for every entries_* table).
--
-- ## recorded_at is the only anchor
--
-- No producer-asserted timestamp crosses the SupplyObserver port, so
-- this table carries only the DB write time.

CREATE TABLE entries_supply_probes (
    event_id        uuid         PRIMARY KEY,
    supply_id       uuid         NOT NULL,
    source_kind     text         NOT NULL CHECK (length(source_kind) BETWEEN 1 AND 50),
    source_id       text         NOT NULL CHECK (length(source_id) BETWEEN 1 AND 200),
    reach_tier      text         NOT NULL CHECK (length(reach_tier) BETWEEN 1 AND 32),
    status_claimed  boolean      NOT NULL,
    recorded_at     timestamptz  NOT NULL DEFAULT now()
);

COMMENT ON COLUMN entries_supply_probes.reach_tier IS
    'RELAYED or UNREACHED in v1. A stronger direct-round-trip tier is reserved and unused; see the migration header.';

-- Supports the coverage read: latest probe per Supply via
-- MAX(recorded_at) / ORDER BY recorded_at DESC LIMIT 1.
CREATE INDEX entries_supply_probes_supply_recorded_idx
    ON entries_supply_probes (supply_id, recorded_at DESC);

-- cora_app has no table-level default privileges in this database (only
-- ALTER DEFAULT PRIVILEGES ... ON SEQUENCES exists); grant explicitly
-- rather than repeating the false "inherits via ALTER DEFAULT
-- PRIVILEGES" claim several other entries_* migration headers carry.
GRANT SELECT, INSERT ON entries_supply_probes TO cora_app;

-- Append-only at the role level (project_immutability_guarantee.md):
-- this removes mutation privileges so the append-only shape cannot be
-- silently broken.
REVOKE UPDATE, DELETE, TRUNCATE ON entries_supply_probes FROM cora_app; -- atlas:safety:allow=append-only revoke, not destructive DDL

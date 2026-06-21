-- Feeder-health heartbeat: append-only liveness pings for the stall rule.
--
-- See [[project_observation_signal_port_design]] decision F. Rule R
-- (rate-dropout / stall) must distinguish a genuinely quiet channel from
-- a DEAD feeder: a feeder that stops emitting must NOT read as a calm
-- run. The feeder runtime inserts one heartbeat row per drain tick
-- regardless of whether any observation flowed; read_feed_health reads
-- MAX(recorded_at) and the decider treats a heartbeat older than the
-- operator-config ceiling (or no heartbeat at all) as cannot-tell ->
-- defer. So a dead feeder disables the stall flag rather than letting an
-- absent channel masquerade as a stall.
--
-- ## Append-only INSERT, not UPSERT
--
-- One row per drain tick (not last-write-wins on a (run_id, source_id)
-- key). An UPSERT would need UPDATE, which the append-only cora_app role
-- is REVOKEd from (test_migration_revokes enforces this for every
-- entries_* table). Reading MAX(recorded_at) gives the same "newest
-- heartbeat" answer with no mutable state. Retention sweeps prune old
-- ping rows (same posture as the other entries_* tables; BRIN-friendly).
--
-- ## Freshness keys on recorded_at, not heartbeat_at
--
-- recorded_at (DEFAULT now(), CORA write time) is the trust anchor;
-- heartbeat_at is the producer-asserted ping time, kept for forensics
-- only. Same spoof-resistance the observation arrival math uses.

CREATE TABLE entries_run_feed_heartbeats (
    event_id     uuid         PRIMARY KEY,
    run_id       uuid         NOT NULL,
    source_id    text         NOT NULL CHECK (length(source_id) BETWEEN 1 AND 255),
    heartbeat_at timestamptz  NOT NULL,
    recorded_at  timestamptz  NOT NULL DEFAULT now()
);

-- Supports read_feed_health: newest heartbeat for a Run via
-- MAX(recorded_at) / ORDER BY recorded_at DESC LIMIT 1.
CREATE INDEX entries_run_feed_heartbeats_run_recorded_idx
    ON entries_run_feed_heartbeats (run_id, recorded_at DESC);

-- Append-only at the role level (project_immutability_guarantee.md):
-- cora_app gets SELECT + INSERT via ALTER DEFAULT PRIVILEGES; this REVOKE
-- removes UPDATE / DELETE / TRUNCATE so the append-only shape cannot be
-- silently broken. Mirrors entries_run_observations and the other
-- entries_* tables.
REVOKE UPDATE, DELETE, TRUNCATE ON entries_run_feed_heartbeats FROM cora_app;

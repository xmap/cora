-- Run BC projection: which in-flight runs is an actor behind?
--
-- Folds TWO streams into one read model (CORA's first cross-BC
-- projection): the Run lifecycle stream and the Decision stream
-- (RunSupervision-context DecisionRegistered only). Backs the
-- authority-revocation kill-switch: when an actor's grant is revoked
-- (Trust revoke_grant), a compensation subscriber looks up that actor's
-- in-flight runs here and holds them.
--
-- Two involvement kinds per (actor, run):
--   - starter:    the actor who started the run (RunStarted envelope
--                 principal_id; RunStarted carries no actor in payload)
--   - supervisor: an actor who authored a RunSupervision Decision linked
--                 to the run (e.g. the RunSupervisor agent)
--
-- Subscribed events:
--   - RunStarted          -> INSERT (involvement_kind=starter, status=Running)
--   - RunHeld             -> UPDATE status=Held         (all rows for run_id)
--   - RunResumed          -> UPDATE status=Running      (all rows for run_id)
--   - RunCompleted        -> UPDATE status=Completed    (terminal)
--   - RunAborted          -> UPDATE status=Aborted      (terminal)
--   - RunStopped          -> UPDATE status=Stopped      (terminal)
--   - RunTruncated        -> UPDATE status=Truncated    (terminal)
--   - DecisionRegistered  -> (context=RunSupervision only) INSERT
--                            (involvement_kind=supervisor) at the run's
--                            current status; RunStarted always precedes it
--                            in global event order.
--
-- The partial index serves the sole query: "in-flight runs for actor X"
-- (status IN Running|Held). Terminal rows stay in the table (audit) but
-- fall out of the index. Mutable read model: cora_app gets full DML (this
-- is a proj_* table, not an append-only events/entries_* table, so no
-- REVOKE).

CREATE TABLE proj_run_actor_involvement (
    actor_id          UUID        NOT NULL,
    run_id            UUID        NOT NULL,
    involvement_kind  TEXT        NOT NULL CHECK (
        involvement_kind IN ('starter', 'supervisor')
    ),
    status            TEXT        NOT NULL CHECK (
        status IN ('Running', 'Held', 'Completed', 'Aborted', 'Stopped', 'Truncated')
    ),
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (actor_id, run_id, involvement_kind)
);

-- Serves "in-flight runs for actor X": the only read the kill-switch
-- lookup issues. Partial on the two non-terminal statuses so terminal
-- rows (kept for audit) do not bloat the index.
CREATE INDEX proj_run_actor_involvement_actor_inflight_idx
    ON proj_run_actor_involvement (actor_id)
    WHERE status IN ('Running', 'Held');

-- Status UPDATEs touch all rows of a run_id (starter + any supervisors),
-- so an index on run_id keeps that fan-out cheap.
CREATE INDEX proj_run_actor_involvement_run_idx
    ON proj_run_actor_involvement (run_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_run_actor_involvement TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_run_actor_involvement')
ON CONFLICT DO NOTHING;

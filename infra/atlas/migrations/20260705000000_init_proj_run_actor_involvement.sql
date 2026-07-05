-- Kill-switch K2: the actor-involvement resolver read model.
--
-- Answers "which in-flight Runs does principal P drive?" so the
-- authority-revocation holder subscriber (K3) can hold a revoked
-- principal's runs. Folded from Run lifecycle events; the STARTER is
-- the RunStarted event's ENVELOPE principal_id (the Authorize-gated
-- issuer), not a payload field.
--
-- Involvement scope is STARTER-ONLY for v1, structured extensible: the
-- `involvement_role` column carries 'starter' today and reserves
-- 'supervisor' so a later additive fold (the HoldRun / ResumeRun
-- envelope principals) widens "drives" to "started or supervises"
-- without a schema migration.
--
-- Subscribed events:
--   RunStarted   -> INSERT (role='starter', status='Running')
--   RunHeld      -> UPDATE status='Held'    (still in-flight)
--   RunResumed   -> UPDATE status='Running'
--   RunCompleted -> UPDATE status='Completed'  (terminal, no longer driven)
--   RunAborted   -> UPDATE status='Aborted'    (terminal)
--   RunStopped   -> UPDATE status='Stopped'    (terminal)
--   RunTruncated -> UPDATE status='Truncated'  (terminal)
--
-- "In-flight" (what the lookup returns) = status IN ('Running', 'Held').
-- Terminal rows are retained (not deleted) so the resolver stays a pure
-- fold and an audit of past involvement survives.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_run_actor_involvement (
    principal_id      UUID        NOT NULL,
    run_id            UUID        NOT NULL,
    involvement_role  TEXT        NOT NULL DEFAULT 'starter' CHECK (
        involvement_role IN ('starter', 'supervisor')
    ),
    status            TEXT        NOT NULL CHECK (
        status IN ('Running', 'Held', 'Completed', 'Aborted', 'Stopped', 'Truncated')
    ),
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (principal_id, run_id)
);

-- The lookup's hot path: in-flight runs for one principal.
CREATE INDEX proj_run_actor_involvement_principal_idx
    ON proj_run_actor_involvement (principal_id, status);

-- Lifecycle UPDATEs arrive keyed by run_id (the event has the run, the
-- projection must find every involvement row for it).
CREATE INDEX proj_run_actor_involvement_run_idx
    ON proj_run_actor_involvement (run_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_run_actor_involvement TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_run_actor_involvement')
ON CONFLICT DO NOTHING;

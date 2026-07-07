-- Consequence gate (Gate IV): the ratification-coverage read model.
--
-- Answers "is action (target_action_id, command_name) covered by a GRANTED
-- Ratification?" so Run BC's stop_run gate (via the ConsequenceLookup port) can
-- admit a consequence-classed command only after a second, independent principal
-- has co-signed. The target action is the run being stopped, so the consumer
-- passes run_id as target_action_id.
--
-- Folded from Ratification events. The scope keys (target_action_id,
-- command_name) live only on the genesis RatificationRequested; Granted/Denied
-- carry ratification_id alone, so the projection carries the scope from genesis
-- and folds status forward by ratification_id:
--   RatificationRequested -> INSERT (status='Requested')
--   RatificationGranted   -> UPDATE status='Granted'
--   RatificationDenied    -> UPDATE status='Denied'
--
-- The lookup filters to status='Granted'. Denied/Requested rows are retained
-- (auditable); coverage keys on status, not row presence.
--
-- Mutable read model. cora_app gets full DML.

CREATE TABLE proj_trust_ratification_coverage (
    ratification_id   UUID        PRIMARY KEY,
    target_action_id  UUID        NOT NULL,
    command_name      TEXT        NOT NULL,
    status            TEXT        NOT NULL CHECK (
        status IN ('Requested', 'Granted', 'Denied')
    ),
    created_at        TIMESTAMPTZ NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The lookup's hot path: is (target_action_id, command_name) Granted?
CREATE INDEX proj_trust_ratification_coverage_scope_idx
    ON proj_trust_ratification_coverage (target_action_id, command_name, status);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_trust_ratification_coverage TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_trust_ratification_coverage')
ON CONFLICT DO NOTHING;

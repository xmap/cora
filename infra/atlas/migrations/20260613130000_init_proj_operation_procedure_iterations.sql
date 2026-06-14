-- Per-iteration convergence read model for first-class Procedure iteration.
--
-- One row per (procedure_id, iteration_index), fed by the iteration
-- boundary events already on the Procedure stream:
--   ProcedureIterationStarted -> INSERT (procedure_id, iteration_index, started_at)
--   ProcedureIterationEnded   -> UPDATE ended_at / converged / reason
-- The convergence verdict (converged/reason) is already durable on the
-- event log, so this is a rebuildable, mutable projection (truncate +
-- replay re-derives it), NOT an immutable system-of-record entries_*
-- table. It mirrors the multi-row projection family
-- (proj_decision_ratings, proj_equipment_frame_children): composite PK,
-- skinny columns, fed by domain events, replay-safe.
--
-- It answers, in plain SQL, the questions the single-row
-- proj_operation_procedure_summary.iteration_count denorm cannot:
--   - which iterations converged        (WHERE converged)
--   - time per iteration                (ended_at - started_at)
--   - convergence rate                  (COUNT(converged) / COUNT(*))
--
-- Schema decisions:
--   - Composite PK (procedure_id, iteration_index): one row per
--     iteration. ON CONFLICT DO NOTHING on the Started arm makes the
--     INSERT replay-safe; the Ended arm UPDATEs by PK.
--   - started_at NOT NULL (Started always lands first); ended_at NULL
--     while the iteration is open.
--   - converged BOOLEAN (true / false / NULL = no verdict);
--     reason TEXT NULL (operator note, trimmed at the decider).
--   - Index (procedure_id, started_at) for ordered drill-down /
--     time-per-iteration. Partial index (converged) WHERE converged IS
--     NOT NULL for convergence-rate filters.
--
-- The column shape deliberately equals the body a future
-- entries_operation_procedure_iterations substream would carry, so the
-- item-5 promotion (>100 iterations/run) is a write-tier shift with no
-- event-shape change.
--
-- Mutable read model; cora_app needs full DML. Bookmark row inserted at
-- sentinel so the worker replays full history on first advance.

CREATE TABLE proj_operation_procedure_iterations (
    procedure_id    UUID        NOT NULL,
    iteration_index INTEGER     NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    converged       BOOLEAN,
    reason          TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (procedure_id, iteration_index)
);

CREATE INDEX proj_operation_procedure_iterations_by_started_idx
    ON proj_operation_procedure_iterations (procedure_id, started_at);

CREATE INDEX proj_operation_procedure_iterations_converged_idx
    ON proj_operation_procedure_iterations (converged)
    WHERE converged IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_operation_procedure_iterations TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_operation_procedure_iterations')
ON CONFLICT DO NOTHING;

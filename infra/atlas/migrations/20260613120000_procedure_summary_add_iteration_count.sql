-- Procedure summary projection: additive iteration_count column.
--
-- First-class Procedure iteration (ProcedureIterationStarted /
-- ProcedureIterationEnded boundary pair). The ProcedureSummaryProjection
-- subscribes to ProcedureIterationStarted and folds the operator-supplied
-- iteration_index into this denorm so "how many iterations did this
-- alignment take" is a plain SQL question instead of a per-kind jsonb dig
-- into the free-form activity evidence.
--
-- Additive evolution: existing rows default to 0 (no iterations begun).
-- NOT NULL DEFAULT 0 with CHECK (iteration_count >= 0) mirrors the
-- proj_calibration_summary.revision_count incrementing-count precedent.
--
-- Mutable read model. cora_app keeps its existing DML grants on
-- proj_operation_procedure_summary.

ALTER TABLE proj_operation_procedure_summary
    ADD COLUMN iteration_count INTEGER NOT NULL DEFAULT 0 CHECK (iteration_count >= 0);

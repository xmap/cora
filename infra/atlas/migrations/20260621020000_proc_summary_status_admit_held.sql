-- Procedure summary projection: admit 'Held' in the status CHECK.
--
-- Tier-1 resumable conduct landed the Held/Resumed FSM (ProcedureHeld /
-- ProcedureResumed) and try_conduct_procedure makes a Held Procedure
-- operator-reachable. The summary read model can now surface it: widen the
-- status CHECK so the ProcedureSummaryProjection can fold ProcedureHeld into
-- status='Held'. ProcedureResumed maps back to 'Running', so 'Held' is the
-- only new persisted status value.
--
-- The init migration declared the CHECK inline on the column, so Postgres
-- auto-named it proj_operation_procedure_summary_status_check. Drop + re-add
-- with the widened value set. Loosening a CHECK is non-destructive: no
-- existing row (one of the 5 prior statuses) can violate the wider set, so
-- this needs no backfill and no data-safety opt-out.
--
-- Forward-only: a rollback is a new compensating migration. Mutable read
-- model; cora_app keeps its existing DML grants.

ALTER TABLE proj_operation_procedure_summary
    DROP CONSTRAINT proj_operation_procedure_summary_status_check;

ALTER TABLE proj_operation_procedure_summary
    ADD CONSTRAINT proj_operation_procedure_summary_status_check
    CHECK (status IN ('Defined', 'Running', 'Held', 'Completed', 'Aborted', 'Truncated'));

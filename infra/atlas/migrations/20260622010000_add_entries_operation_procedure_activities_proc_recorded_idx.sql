-- Procedure-scoped, recorded_at-keyed index for the ProcedureWatcher fold.
--
-- See [[project-procedure-watcher-design]]. The ProcedureActivityLookup
-- read port serves one query, keyed on recorded_at (the CORA write-time
-- trust anchor, not the spoofable sampled_at) and procedure-scoped:
--
--   - read_procedure_activity_recency:
--     SELECT max(recorded_at) WHERE procedure_id = $1
--
-- This composite btree is LOAD-BEARING for the anti-false-flag fold: the
-- pre-existing indexes on entries_operation_procedure_activities are
-- keyed on sampled_at (plus a BRIN on recorded_at), so none serves a
-- procedure-scoped max(recorded_at) without scanning the procedure's full
-- activity history. The DESC ordering lets the planner satisfy the
-- aggregate from the index head.
--
-- Additive + forward-only; CREATE INDEX IF NOT EXISTS so a re-run is a
-- no-op. (Not CONCURRENTLY: Atlas wraps each migration file in a
-- transaction, matching every existing index migration in this repo.)

CREATE INDEX IF NOT EXISTS entries_operation_procedure_activities_proc_recorded_idx
    ON entries_operation_procedure_activities (procedure_id, recorded_at DESC);

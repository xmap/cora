-- Slice 4 fix: rename projection column to match the state-field rename.
--
-- The Slice 4 rename (ProcedureStep -> Activity) updated:
--   - State field `steps_logbook_id` -> `activity_logbook_id`
--   - Projection writer SQL (apps/api/src/cora/operation/projections/procedure.py)
--     to write `activity_logbook_id`
-- but missed the projection-table DDL, which still defined the column as
-- `steps_logbook_id` (from migration 20260515160000). CI surfaced this as
-- UndefinedColumnError across 12+ integration tests that exercise the
-- procedure-summary projection.
--
-- Forward-only fix: rename the column. Non-destructive (Postgres preserves
-- the column data through RENAME COLUMN).

ALTER TABLE proj_operation_procedure_summary
    RENAME COLUMN steps_logbook_id TO activity_logbook_id;

-- Procedure summary projection: additive hold_causes column.
--
-- `status = 'Held'` is one bit and cannot say WHICH concern is holding, so
-- every hold was clocked against one week-long staleness window on the
-- assumption that a hold is a deliberate operator pause. A conduct the
-- Conductor parked on a step fault is the opposite: nothing will move it
-- without a person, and a week of silence is exactly wrong for it.
--
-- The Procedure aggregate now records its hold claims, so this denorms the
-- CAUSES onto the read model and the ProcedureWatcher selects its window per
-- row instead of per status. Causes rather than a precomputed
-- "needs attention" flag: the classification lives in
-- `ATTENTION_HOLD_CAUSES`, and baking it into the projection would leave old
-- rows silently wrong the day that set changes.
--
-- Ordered oldest-first, mirroring `Procedure.hold_claims`. Maintained by the
-- Held (append, deduplicated) / HoldClaimReleased (remove) / Resumed and the
-- three terminal arms (clear) of ProcedureSummaryProjection.
--
-- Backfill: a row Held right now was held before causes were recorded, which
-- is what the aggregate folds to `LEGACY_CAUSE`, so the denorm says the same
-- rather than claiming (with an empty array) that nothing holds it. A
-- projection rebuild replaces these with the real causes where the stream has
-- them.
--
-- Mutable read model. cora_app keeps its existing DML grants on
-- proj_operation_procedure_summary.

ALTER TABLE proj_operation_procedure_summary
    ADD COLUMN hold_causes TEXT[] NOT NULL DEFAULT '{}';

UPDATE proj_operation_procedure_summary
SET hold_causes = ARRAY['legacy-unscoped']
WHERE status = 'Held';

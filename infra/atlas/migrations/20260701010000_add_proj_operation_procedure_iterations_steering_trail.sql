-- TIER-1 replay: surface the steering decision trail on the per-iteration
-- read model.
--
-- proj_operation_procedure_iterations already carries the convergence verdict
-- (converged / reason). A steered conduct (conduct_until_advised) additionally
-- records, per iteration, what the brain advised: whether to stop, which brain
-- decided, and the coordinate it advised for the next pass. These are already
-- durable on the ProcedureIterationEnded event; this adds the projection
-- columns so a finished GP-steered run's decision trail is readable (a
-- non-deterministic brain cannot be faithfully reconstructed by RE-ASKING, so
-- reading the recorded trail is the reconstruction path).
--
--   - advised_stop        BOOLEAN  (true advised-stop / false continue /
--                                   NULL no-verdict = plain convergence pass)
--   - model_ref           TEXT     (the deciding brain, e.g. 'botorch')
--   - advised_next_point  JSONB    (SteeringPoint.coordinates map the brain
--                                   advised for the next pass; NULL on a Stop
--                                   verdict + on non-steered iterations)
--
-- All nullable + additive: plain convergence iterations and pre-TIER-1 rows
-- leave them NULL. Mutable projection (truncate + replay re-derives), so no
-- REVOKE; cora_app already holds full DML on this table.

ALTER TABLE proj_operation_procedure_iterations
    ADD COLUMN advised_stop       BOOLEAN,
    ADD COLUMN model_ref          TEXT,
    ADD COLUMN advised_next_point JSONB;

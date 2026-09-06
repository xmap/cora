-- Measure how long the brain took to answer, per steered iteration.
--
-- Wall clock is the one budget dimension nothing watches. Money and tokens are
-- gated at both enforcement tiers (the coarse post-hoc _budget_gate for the
-- serialized subscribers, the pre-estimate BudgetSpendGuard for the autonomous
-- steering caller), but a Gaussian process spends neither, so every existing
-- gate is blind to it. At a beamline the scarce resource is beam time: a brain
-- taking thirty seconds per advice call across forty passes burns twenty
-- minutes of allocation and nothing currently notices.
--
-- This column is measurement only. No cap is enforced anywhere yet; the point
-- is to find out whether the problem is real at 2-BM before deciding whether a
-- wall-clock cap belongs on the brain, the Procedure or the Allocation.
--
--   - advice_latency_ms  DOUBLE PRECISION  (milliseconds the DecidePort took to
--                                           return, measured by the Conductor
--                                           off its injected clock, floored at
--                                           zero; recorded on both the advised
--                                           and the brain-faulted paths)
--
-- Nullable + additive: plain convergence iterations and every pre-existing row
-- leave it NULL. Mutable projection (truncate + replay re-derives), so no
-- REVOKE; cora_app already holds full DML on this table.

ALTER TABLE proj_operation_procedure_iterations
    ADD COLUMN advice_latency_ms DOUBLE PRECISION;

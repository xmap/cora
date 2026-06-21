-- Precomputed closed-loop rule inputs on the Run summary projection.
--
-- See [[project_observation_signal_port_design]] decision D. The two
-- closed-loop rules need a per-Run scalar each: snr_limit (Rule Q, the
-- operator-SET quality limit) and expected_observation_interval_seconds
-- (Rule R, the expected inter-arrival the stall gap is measured against).
-- Both are derived ONCE at start_run from the already-validated
-- effective_parameters and recomputed on RunAdjusted, so the supervisor
-- reads an O(1) projection column each tick instead of a per-Running-run
-- fold (the supervisor does ZERO per-Running-run folds today; a fold per
-- tick would add new stream-replay I/O on the common case).
--
-- Both NULLABLE. NULL deterministically DISABLES the corresponding rule
-- for that Run (cannot-tell -> defer), which is the fail-safe default for
-- Methods whose parameters_schema does not declare the key, and the
-- degenerate-value guard (non-positive / non-finite stored as NULL).
-- Additive + forward-only; existing rows read NULL (rules off).

ALTER TABLE proj_run_summary
    ADD COLUMN snr_limit double precision,
    ADD COLUMN expected_observation_interval_seconds double precision;

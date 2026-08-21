-- Add the GPU-seconds column a LocalLLM call has always measured
-- (`cora.agent.llm.gpu.seconds`, an OpenTelemetry histogram) but the
-- ledger has never stored.
--
-- Why now: in-house serving prices at $0/token by design, which is
-- correct, but that pricing choice is invisible on this row today. A
-- reasoning entry from LocalLLM and one from a paid vendor API both
-- show near-zero cost_usd, with nothing distinguishing "free by policy"
-- from "no GPU time was actually consumed". The same gap was closed for
-- cache-token accounting earlier; this closes the last such sibling.
--
-- Nullable DOUBLE PRECISION, mirroring cost_usd on this same table: an
-- adapter that never touches a GPU (every vendor-API adapter) leaves it
-- NULL, which is the honest value, not 0.
--
-- Deliberately NOT a dollar figure. A shadow-cost column derived from
-- the facility's GPU-hour rate would price this call at write time, and
-- that rate is a configuration value that can change; a historical row
-- would then lie about what the call cost when it actually ran. Only
-- the raw seconds primitive is durable here. A reader who wants a
-- shadow cost recomputes it from this column against whatever rate is
-- current when they ask, the same way `cora.agent.llm.gpu.shadow_cost.usd`
-- is derived at observe time today and never persisted.
--
-- Forward-only per project_forward_only_migrations: rollback is a new
-- compensating migration, never an edit here.

ALTER TABLE entries_decision_inferences
    ADD COLUMN gpu_seconds DOUBLE PRECISION;

COMMENT ON COLUMN entries_decision_inferences.gpu_seconds IS
    'Occupancy-share GPU-seconds a LocalLLM call consumed, mirroring the cora.agent.llm.gpu.seconds histogram (no OTel attribute exists for GPU time). NULL means no LocalLLM served this call, not zero GPU time. The raw primitive, not a priced shadow cost: the facility''s GPU-hour rate can change over time, and pricing at write time would make a historical row lie about what it cost when it ran.';

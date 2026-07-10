-- Add cost_usd to entries_decision_inferences: the actual dollar cost of the
-- LLM call each inference entry records.
--
-- The per-call cost was already computed at the adapter (compute_cost_usd from
-- usage tokens x PRICING) but only emitted to the cora.agent.llm.cost.usd
-- histogram and then discarded: the meter existed, the ledger sink did not.
-- Budget enforcement (the AgentBudget monthly_usd_cap gate, unpaused
-- 2026-07-11) needs a durable per-(agent, window) spend fact to sum, and the
-- inference entry is its natural home: it already carries agent_id,
-- occurred_at, and the token counts the cost derives from, so spend attribution
-- rides the existing provenance row instead of a parallel table.
--
-- Additive forward-only migration, nullable with NO default: legacy rows keep
-- cost_usd IS NULL ("cost not recorded then", distinct from a true $0 call),
-- and the spend lookup COALESCEs NULL to 0 so pre-migration history never
-- inflates a balance. DOUBLE PRECISION matches the float the producer computes;
-- sub-cent drift is irrelevant at cap granularity (caps are whole dollars).
-- No index: the spend lookup filters on agent_id + occurred_at, served by the
-- existing entries_decision_inferences indexes; add a covering index only if
-- the gate's read shows up in p95 (deferred-with-trigger).

ALTER TABLE entries_decision_inferences
    ADD COLUMN cost_usd DOUBLE PRECISION;

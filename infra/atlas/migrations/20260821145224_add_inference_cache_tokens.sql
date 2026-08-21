-- Add the two cache-token columns the port already reports (`LLMUsage`
-- has carried `cache_creation_input_tokens` / `cache_read_input_tokens`
-- since caching support landed) but the ledger has never stored.
--
-- Why now: provider-side prompt caching changes what a call COSTS and
-- what its token counts REPORT without changing what the ledger's
-- input_tokens/output_tokens columns show. A four-arm debrief comparison
-- over the same prompt exposed this directly: two arms reported roughly
-- a sixth of another's input tokens for an IDENTICAL prompt, while
-- costing more than their visible tokens imply. The recorded cost stays
-- correct (the pricing math consumes the provider's own accounting), but
-- the record cannot EXPLAIN the discrepancy: two rows for the same
-- prompt can show different token counts and different costs with
-- nothing on either row accounting for the difference. That is an
-- auditability gap in a ledger whose whole purpose is to be audited.
--
-- Both columns are nullable BIGINT, mirroring input_tokens/output_tokens
-- on this same table: a provider that never reports cache stats (or a
-- call that never used caching) leaves them NULL, which is the honest
-- value, not 0. `LLMUsage` itself defaults the in-memory value to 0 when
-- a provider is silent, but the ledger column stays NULL until a
-- producer actually reports a number, matching how every other optional
-- OTel column on this table behaves.
--
-- Forward-only per project_forward_only_migrations: rollback is a new
-- compensating migration, never an edit here.

ALTER TABLE entries_decision_inferences
    ADD COLUMN cache_creation_input_tokens BIGINT,
    ADD COLUMN cache_read_input_tokens     BIGINT;

COMMENT ON COLUMN entries_decision_inferences.cache_creation_input_tokens IS
    'gen_ai.usage.cache_creation_input_tokens equivalent: tokens the provider billed to WRITE a cache entry on this call. NULL means the provider reported nothing, not that no tokens were spent.';
COMMENT ON COLUMN entries_decision_inferences.cache_read_input_tokens IS
    'gen_ai.usage.cache_read_input_tokens equivalent: tokens the provider served from an existing cache entry, billed at a different rate than input_tokens. NULL means the provider reported nothing.';

-- The allocation envelope's read model: one row per Allocation,
-- queried by status. The envelope gate's `PostgresAllocationLookup`
-- asks "which envelope is Active right now?" on every gated LLM call,
-- and the CampaignClosed sealer asks the same question plus the
-- campaign binding; neither is answerable from the event store
-- without a by-status index, which is exactly what a projection is
-- for.
--
-- Balance is deliberately absent: spend folds from
-- entries_decision_inferences at read time (the never-stored-balance
-- stance); only the seal freezes a snapshot (spent_usd_at_seal).
--
-- Mutable read model. cora_app gets full DML. Bookmark seeded so the
-- projection worker advances from genesis on first run.

CREATE TABLE proj_budget_allocation_summary (
    allocation_id      UUID             PRIMARY KEY,
    ceiling_usd        DOUBLE PRECISION NOT NULL CHECK (ceiling_usd > 0),
    campaign_id        UUID,
    note               TEXT             NOT NULL,
    status             TEXT             NOT NULL CHECK (
        status IN ('Granted', 'Active', 'Sealed', 'Voided')
    ),
    granted_at         TIMESTAMPTZ      NOT NULL,
    activated_at       TIMESTAMPTZ,
    sealed_at          TIMESTAMPTZ,
    spent_usd_at_seal  DOUBLE PRECISION,
    created_at         TIMESTAMPTZ      NOT NULL,
    updated_at         TIMESTAMPTZ      NOT NULL DEFAULT now()
);

-- The lookup's query shape: the newest-activated Active envelope.
CREATE INDEX proj_budget_allocation_summary_status_idx
    ON proj_budget_allocation_summary (status, activated_at);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_budget_allocation_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_budget_allocation_summary')
ON CONFLICT DO NOTHING;

-- The facility model catalog's read model: one row per LanguageModel
-- entry, queried by model identity (provider + model), which is the shape
-- both consumers need. The define_agent gate asks "is this model_ref
-- Approved, and at what tiers?" (the shipped fleet's defaults are pinned
-- against the seeds by a unit consistency test, not by any startup
-- check); the at-risk-results surface asks "which entries announced
-- retirement, and were they Pinned or Alias?". Neither question is
-- answerable from the event store without a by-identity index, which is
-- exactly what a projection is for.
--
-- cost_basis is deliberately absent: pricing stays on the aggregate (few
-- entries, config-shaped) so there is exactly one pricing home.
--
-- Mutable read model. cora_app gets full DML. Bookmark seeded so the
-- projection worker advances from genesis on first run.

CREATE TABLE proj_agent_language_model_summary (
    language_model_id        UUID        PRIMARY KEY,
    name                     TEXT        NOT NULL,
    provider                 TEXT        NOT NULL,
    model                    TEXT        NOT NULL,
    snapshot_pin             TEXT,
    served_via               TEXT        NOT NULL CHECK (
        served_via IN ('Direct', 'Argo', 'InHouse')
    ),
    data_tier                TEXT        NOT NULL CHECK (
        data_tier IN ('Open', 'Internal', 'Sensitive')
    ),
    archivability            TEXT        NOT NULL CHECK (
        archivability IN ('Pinned', 'Alias')
    ),
    status                   TEXT        NOT NULL CHECK (
        status IN ('Defined', 'Approved', 'RetirementAnnounced', 'Retired', 'Deprecated')
    ),
    created_at               TIMESTAMPTZ NOT NULL,
    approved_at              TIMESTAMPTZ,
    retirement_announced_at  TIMESTAMPTZ,
    retirement_effective_at  TIMESTAMPTZ,
    retired_at               TIMESTAMPTZ,
    deprecated_at            TIMESTAMPTZ,
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The lookup's query shape: latest entry for a (provider, model) pair.
CREATE INDEX proj_agent_language_model_summary_identity_idx
    ON proj_agent_language_model_summary (provider, model);

CREATE INDEX proj_agent_language_model_summary_keyset_idx
    ON proj_agent_language_model_summary (created_at, language_model_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_agent_language_model_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_agent_language_model_summary')
ON CONFLICT DO NOTHING;

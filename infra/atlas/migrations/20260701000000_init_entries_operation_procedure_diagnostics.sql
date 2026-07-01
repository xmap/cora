-- TIER-2 steering audit: per-Procedure GP-steering diagnostics entry table.
--
-- Fifth concrete entry category in CORA after entries_conduit_traversals,
-- entries_conduit_verdicts, entries_decision_inferences,
-- entries_run_observations, and entries_operation_procedure_activities. The
-- second logbook kind on the Procedure aggregate (kind=LOGBOOK_KIND_DIAGNOSTIC,
-- ProcedureDiagnosticLogbookOpened on the Procedure stream). Each row captures
-- one steered-conduct iteration decided by a learning brain: the fitted GP's
-- summary scalars (per-axis lengthscales, observation noise, acquisition
-- value) in a JSON payload, so a reviewer can reconstruct "why did the brain
-- advise that point" after the run.
--
-- ## Storage strategy: polymorphic + JSON payload (Path C)
--
-- The scalar set diverges by brain / model version and per-row volume is low
-- (one row per steered iteration), with no per-kind analytical read-side
-- projection planned, so a single jsonb `payload` column beats typed sibling
-- columns. Same posture as entries_operation_procedure_activities. The
-- optimizer-specific scalar names live ONLY as keys inside payload, never as
-- columns, keeping optimizer vocabulary out of the schema surface (mirrors the
-- DecidePort purity guard's stance for the in-code seam).
--
-- ## Columns beyond the entry skeleton
--
--   - iteration_index: the steered-conduct iteration this diagnostic explains;
--     joins to the same iteration_index on ProcedureIterationEnded so an
--     auditor can tie a diagnostic row to the decision it justified.
--   - model_ref: the deciding brain that produced the diagnostics (e.g.
--     'botorch'); mirrors the model_ref recorded on ProcedureIterationEnded.
--
-- ## Three timestamps
--
--   - sampled_at: phenomenonTime -- when the brain produced the advice this
--     row explains (the conduct's clock read at decide time)
--   - occurred_at: when the handler appended the entry (Clock port)
--   - recorded_at: when Postgres wrote the row (DEFAULT now())
--
-- ## Why no FK to the Procedure aggregate
--
-- Same rationale as the prior entry tables: aggregates live in the events
-- table, not their own row; FK to (stream_type, stream_id) is non-standard and
-- would force schema coupling. procedure_id references whatever Procedure id
-- was passed; downstream queries join via projections.
--
-- ## Indexes
--
--   - PK on event_id (UNIQUE; idempotency / dedup key; ON CONFLICT DO NOTHING
--     handles producer retries silently)
--   - btree on (procedure_id, iteration_index) -- primary read pattern
--     "diagnostics for this Procedure, ordered by the iteration they explain"
--   - btree on (logbook_id) -- "all entries for this logbook session"
--   - BRIN on recorded_at -- retention sweeps + time-range analytics; cheap,
--     matches the append-mostly access pattern. Same shape as prior entries.

CREATE TABLE entries_operation_procedure_diagnostics (
    event_id            uuid              PRIMARY KEY,
    procedure_id        uuid              NOT NULL,
    logbook_id          uuid              NOT NULL,
    iteration_index     integer           NOT NULL,
    model_ref           text              NOT NULL,
    payload             jsonb             NOT NULL,
    sampled_at          timestamptz       NOT NULL,
    occurred_at         timestamptz       NOT NULL,
    correlation_id      uuid              NOT NULL,
    causation_id        uuid,
    recorded_at         timestamptz       NOT NULL DEFAULT now()
);

CREATE INDEX entries_operation_procedure_diagnostics_proc_iter_idx
    ON entries_operation_procedure_diagnostics (procedure_id, iteration_index);

CREATE INDEX entries_operation_procedure_diagnostics_logbook_idx
    ON entries_operation_procedure_diagnostics (logbook_id);

CREATE INDEX entries_operation_procedure_diagnostics_recorded_at_brin_idx
    ON entries_operation_procedure_diagnostics USING BRIN (recorded_at);

-- Append-only at the role level (project_immutability_guarantee.md): the
-- cora_app role gets SELECT + INSERT via ALTER DEFAULT PRIVILEGES; this REVOKE
-- explicitly removes UPDATE / DELETE / TRUNCATE so a future migration cannot
-- accidentally re-grant them. Mirrors the precedent set by the prior entry
-- tables.
REVOKE UPDATE, DELETE, TRUNCATE ON entries_operation_procedure_diagnostics FROM cora_app;

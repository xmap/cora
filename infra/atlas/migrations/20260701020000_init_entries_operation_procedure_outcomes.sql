-- RESUME: per-Procedure steered-pass outcome entry table.
--
-- Sixth concrete entry category in CORA, and the third logbook kind on the
-- Procedure aggregate (kind=LOGBOOK_KIND_OUTCOME, ProcedureOutcomeLogbookOpened
-- on the Procedure stream), after entries_operation_procedure_activities and
-- entries_operation_procedure_diagnostics. Each row is a SELF-DESCRIBING
-- observation of one steered-conduct pass: the coordinate it measured at (point,
-- the x) AND the measured values there (measurements, the y). Its purpose is
-- RESUME: on restart of a crashed GP-steered run, the optimizer's observation
-- history is rebuilt from these recorded outcomes instead of re-measuring
-- hardware (matching durable-execution replay + ask-tell optimizer resumption:
-- recorded results are replayed, side effects are not re-run). Carrying the
-- point on the row means reconstruction is a sort-then-map with no join to the
-- iteration event, so index gaps left by an abandoned (mid-crash) pass are
-- harmless rather than corrupting a positional pairing.
--
-- ## Storage strategy: polymorphic + JSON payload (Path C)
--
-- The measured value shape is beamline-specific (scalar / array / image /
-- tabular per Measurement.kind) and per-row volume is low (one row per steered
-- iteration), so a single jsonb `measurements` column (a list of Measurement
-- dicts) beats typed sibling columns. Same posture as the sibling logbooks.
--
-- ## Columns beyond the entry skeleton
--
--   - iteration_index: the steered-conduct pass this outcome records; the
--     ascending ORDER key for reconstruction and an audit cross-reference to the
--     ProcedureIterationEnded of the same pass. 0-based; may have gaps after an
--     abandoned (mid-crash) pass, which the sort-then-map reconstruction
--     tolerates.
--   - point (jsonb): the coordinate map the pass measured at (the x). Carried on
--     the row so reconstruction needs no join to advised_next_point.
--   - measurements (jsonb): the list of Measurement dicts the pass produced.
--   - succeeded: whether the pass's acquisition succeeded (a failed pass is a
--     real datum the brain weighs, not a dropped row).
--   - actuation_kind: Physical / Simulated / Hybrid provenance, so a resumed
--     fit can distrust a simulated outcome (nullable: absent on some fakes).
--
-- ## Three timestamps
--
--   - sampled_at: phenomenonTime -- when the pass produced these measurements
--   - occurred_at: when the handler appended the entry (Clock port)
--   - recorded_at: when Postgres wrote the row (DEFAULT now())
--
-- ## Why no FK to the Procedure aggregate
--
-- Same rationale as the prior entry tables: aggregates live in the events
-- table; procedure_id references whatever Procedure id was passed; downstream
-- queries join via projections.
--
-- ## Indexes
--
--   - PK on event_id (idempotency / dedup; ON CONFLICT DO NOTHING on retry)
--   - btree on (procedure_id, iteration_index) -- the resume read pattern
--     "every outcome for this Procedure, ordered by the pass it records"
--   - btree on (logbook_id) -- "all entries for this logbook session"
--   - BRIN on recorded_at -- retention sweeps + time-range; append-mostly.

CREATE TABLE entries_operation_procedure_outcomes (
    event_id            uuid              PRIMARY KEY,
    procedure_id        uuid              NOT NULL,
    logbook_id          uuid              NOT NULL,
    iteration_index     integer           NOT NULL,
    point               jsonb             NOT NULL,
    measurements        jsonb             NOT NULL,
    succeeded           boolean           NOT NULL,
    actuation_kind      text,
    sampled_at          timestamptz       NOT NULL,
    occurred_at         timestamptz       NOT NULL,
    correlation_id      uuid              NOT NULL,
    causation_id        uuid,
    recorded_at         timestamptz       NOT NULL DEFAULT now()
);

CREATE INDEX entries_operation_procedure_outcomes_proc_iter_idx
    ON entries_operation_procedure_outcomes (procedure_id, iteration_index);

CREATE INDEX entries_operation_procedure_outcomes_logbook_idx
    ON entries_operation_procedure_outcomes (logbook_id);

CREATE INDEX entries_operation_procedure_outcomes_recorded_at_brin_idx
    ON entries_operation_procedure_outcomes USING BRIN (recorded_at);

-- Append-only at the role level (project_immutability_guarantee.md): the
-- cora_app role gets SELECT + INSERT via ALTER DEFAULT PRIVILEGES; this REVOKE
-- explicitly removes UPDATE / DELETE / TRUNCATE so a future migration cannot
-- accidentally re-grant them. Mirrors the prior entry tables.
REVOKE UPDATE, DELETE, TRUNCATE ON entries_operation_procedure_outcomes FROM cora_app;

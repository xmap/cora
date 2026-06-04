-- Widen proj_decision_summary with the DecisionChoice value.
--
-- The Decision aggregate's `choice` field (the categorical verdict the
-- Decision lands on, sourced from RUN_DEBRIEF_CHOICES /
-- CAUTION_PROPOSAL_CHOICES / etc.) was projected into payload but
-- never surfaced as a column. Two downstream surfaces need it:
--
--   1. The cross-agent debrief lease (project_run_debriefer_lease_design)
--      emits audit-only `DebriefConflicted` and `CautionDraftConflicted`
--      Decisions on the loser-agent's Decision stream. Without a
--      `choice` column, callers of GET /decisions and the
--      `list_decisions` MCP tool see these audit rows alongside real
--      outcomes with no way to filter them out -- skewing future
--      NoAction-rate / DebriefDeferred-rate analytics.
--
--   2. The 65-75% NoAction target for CautionDrafter (per
--      project_caution_drafter_research) needs a `count(*) GROUP BY
--      choice` query; today that requires reading raw event payloads.
--
-- Two-step add-then-backfill-then-NOT-NULL pattern so existing rows
-- inherit the right choice without a placeholder. The events backfill
-- joins the projection row to its single DecisionRegistered event in
-- the events table. COALESCE keeps the migration safe against the
-- hypothetical edge case where a projection row exists without its
-- source event (shouldn't happen; defensive).
--
-- ## Index
--
-- `(actor_id, choice)` supports the analytic shape "count by choice
-- for a given agent" (e.g., RunDebriefer's NoAction rate is the
-- denominator excluding `DebriefConflicted` rows). Composite over
-- two single-column indexes because both columns ride together in
-- every analytic query that needs `choice`.
--
-- ## Forward-only
--
-- Rollback via a NEW compensating migration per
-- project_forward_only_migrations.

ALTER TABLE proj_decision_summary ADD COLUMN choice TEXT;

UPDATE proj_decision_summary p
SET choice = COALESCE(
    (
        SELECT e.payload->>'choice'
        FROM events e
        WHERE e.stream_type = 'Decision'
          AND e.event_type = 'DecisionRegistered'
          AND e.stream_id = p.decision_id
        LIMIT 1
    ),
    'Unknown'
);

ALTER TABLE proj_decision_summary ALTER COLUMN choice SET NOT NULL;

CREATE INDEX proj_decision_summary_actor_choice_idx
    ON proj_decision_summary (actor_id, choice);

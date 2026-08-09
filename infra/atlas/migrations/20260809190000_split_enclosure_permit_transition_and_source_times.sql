-- Split one timestamp column into the two facts it was conflating.
--
-- `last_observed_at` never held an observation time. The projection
-- writes `payload["occurred_at"]` into it, which is CORA's own clock at
-- the moment the handler appended the event. Its name promised the
-- substrate's time and delivered CORA's, and that is the whole defect:
-- a reader cannot tell the two apart, and at APS 2-BM they are far
-- apart, because both PSS permit signals report no time at all.
--
-- After this migration the table reads as two coherent groups:
--
--   CORA's record of the transition
--     last_permit_status_changed_at, last_permit_status_reason,
--     last_trigger
--   the substrate's attribution
--     last_source_kind, last_source_id, last_source_observed_at
--
-- Naming follows the skeleton five sibling projections already share
-- (`last_<axis>_changed_at` + `last_<axis>_reason` + `last_trigger`,
-- all written from `occurred_at`): proj_supply_summary,
-- proj_safety_clearance_summary, proj_caution_summary,
-- proj_campaign_summary, proj_operation_procedure_summary. Enclosure
-- was the sole outlier. The axis is spelled out because Enclosure has
-- TWO status axes and `decommissioned_at` is a change on the other one
-- that does not touch these columns.
--
-- No data movement. Every existing row already holds ingest time in the
-- renamed column, so the rename makes the existing values correctly
-- labelled rather than moving them. `last_source_observed_at` starts
-- NULL for every historic row and that is the true value, not a
-- placeholder: the payloads those rows were built from never carried a
-- substrate time, so there is nothing to backfill and nothing to fake.
--
-- DEPLOY ORDER, and it is the opposite of the project default.
-- `docs/stack/deployment.md` says apply migrations first, then roll the
-- image. That is right for additive DDL and wrong here: a running old
-- image selects `last_observed_at` in three statements
-- (`postgres_enclosure_lookup.py`) and updates it in the projection, so
-- between the migration and the rollout every enclosure lookup raises
-- UndefinedColumnError, which fails the start_run / start_procedure
-- pre-flight closed, and the projection batch rolls back forever
-- without advancing its bookmark. STOP the API, apply, then START it.
-- Rollback is a new forward migration renaming back, per the
-- forward-only rule; the schema-version boot gate already refuses to
-- start a pre-rename image against a post-rename database.

ALTER TABLE proj_enclosure_summary
    RENAME COLUMN last_observed_at TO last_permit_status_changed_at;

ALTER TABLE proj_enclosure_summary
    RENAME COLUMN last_observed_reason TO last_permit_status_reason;

ALTER TABLE proj_enclosure_summary
    ADD COLUMN last_source_observed_at TIMESTAMPTZ;

COMMENT ON COLUMN proj_enclosure_summary.last_permit_status_changed_at IS
    'CORA ingest time of the last permit-status CHANGE, from the event''s '
    'occurred_at (Clock port at handler-append). Advances only on a change: '
    'the decider returns no events for an identical-status observation, so a '
    'steady hutch leaves this frozen. A stale value therefore means "no '
    'transition since", never "not observed since".';

COMMENT ON COLUMN proj_enclosure_summary.last_source_observed_at IS
    'The substrate''s own time for the reading behind that change, or NULL '
    'when the substrate reported none. NULL is the ordinary case, not a gap: '
    'at APS 2-BM both PSS permit PVs report an undefined EPICS stamp on every '
    'update. Never populated from a CORA clock; an adapter with no substrate '
    'time reports absence instead.';

COMMENT ON COLUMN proj_enclosure_summary.last_permit_status_reason IS
    'Operator-supplied or adapter-supplied reason recorded with the last '
    'permit-status change. Renamed from last_observed_reason alongside its '
    'sibling so the transition group keeps one prefix.';

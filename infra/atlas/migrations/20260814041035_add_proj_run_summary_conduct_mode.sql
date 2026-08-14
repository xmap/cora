-- Who drove this Run's act: CORA's own Conductor, or an external tool
-- CORA only observes. See cora.run.aggregates.run.state.ConductMode.
--
-- NOT NULL DEFAULT 'Conducted': unlike the nullable snr_limit /
-- expected_observation_interval_seconds columns, "no value" is not a
-- legitimate state for this axis. Every Run genesis at the time this
-- migration was written really was Conducted (nothing in the codebase
-- constructed a Witnessed-mode Run yet), so backfilling existing rows
-- to 'Conducted' is a true fact, not a guess. Additive + forward-only;
-- immutable after genesis by aggregate-level invariant, same as
-- pinned_calibration_ids.

ALTER TABLE proj_run_summary
    ADD COLUMN conduct_mode text NOT NULL DEFAULT 'Conducted';

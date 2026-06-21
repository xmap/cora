-- Add running_since to proj_run_summary: the timestamp the current Running
-- interval began.
--
-- The RunLivenessWatchdog (shadow rule in the RunSupervisor loop) flags a Run
-- that has been Running for an implausibly long time without progressing. It
-- needs an un-contaminated Running-duration signal: now() - running_since.
--   - created_at measures wall-clock-since-submission and over-counts overnight
--     Held intervals, so it would false-alarm (the failure the design warns
--     against); updated_at is reset by every status transition and is not on
--     the list read surface.
-- So running_since is set on RunStarted (the Running transition) and RESET on
-- RunResumed (the held->running transition), tracking only actual Running time.
--
-- Additive forward-only migration, nullable with NO default: legacy rows (and
-- any Run already Running at deploy time) land with running_since IS NULL, and
-- the watchdog treats NULL as "cannot evaluate" -> never flags. No index: the
-- watchdog reads running_since per-Run from the row the supervisor already
-- fetched via list_runs; no query filters or orders on it.
--
-- Projection's apply() is updated in the same commit
-- (cora.run.projections.summary): RunStarted INSERT sets running_since =
-- occurred_at, and a new RunResumed arm sets status='Running' + running_since =
-- occurred_at.

ALTER TABLE proj_run_summary
    ADD COLUMN running_since TIMESTAMPTZ;

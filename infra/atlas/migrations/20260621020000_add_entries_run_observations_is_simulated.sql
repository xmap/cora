-- Per-observation simulation provenance for the closed-loop read seam.
--
-- See [[project_observation_signal_port_design]] decision C: a closed-loop
-- rule (quality-within-limits, rate-dropout) must never act on simulated
-- data as if it were real. The flag travels WITH the datum (not a route
-- registry: observations key on operator channel_name, not a substrate
-- address, and the same channel can carry real data on one Run and sim
-- data on another). A single boolean (not the 3-value PHYSICAL/SIMULATED/
-- HYBRID enum) is right: one row has exactly one origin; the window-level
-- mixed case is an OR-fold on the read side.
--
-- Additive + forward-only: NOT NULL DEFAULT false means every existing
-- and human-entered row reads real. Only a sim / replay feeder sets it
-- True. The production read path filters is_simulated = false, so a rule
-- structurally cannot read sim data as real. The read-side mirror of the
-- Operation BC's ActuationKind 'any simulator touch disqualifies' gate.
--
-- entries_run_observations stays append-only (the REVOKE from
-- 20260514040000 / the rename in 20260610020000 still holds); ADD COLUMN
-- with a constant default is a metadata-only change, no row rewrite.

ALTER TABLE entries_run_observations
    ADD COLUMN is_simulated boolean NOT NULL DEFAULT false;

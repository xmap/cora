-- Channel-scoped, recorded_at-keyed index for the closed-loop read seam.
--
-- See [[project_observation_signal_port_design]] decision A. The
-- RunChannelLookup read port serves two queries, both keyed on
-- recorded_at (the CORA write-time trust anchor, not the spoofable
-- sampled_at) and both channel-scoped:
--
--   - read_run_channel_latest: WHERE run_id = $1 AND channel_name = $2
--     ORDER BY recorded_at DESC LIMIT 1  (Rule Q point read)
--   - read_run_channel_window: WHERE run_id = $1 AND channel_name = $2
--     AND recorded_at > $3  (Rule R windowed count_since)
--
-- This composite btree is LOAD-BEARING, not a tuning nicety: the
-- pre-existing indexes on entries_run_observations are keyed on
-- sampled_at (plus a BRIN on recorded_at) and carry no channel_name, so
-- none of them serves a channel-scoped ORDER BY / range on recorded_at.
--
-- Additive + forward-only; CREATE INDEX IF NOT EXISTS so a re-run is a
-- no-op. (Not CONCURRENTLY: Atlas wraps each migration file in a
-- transaction, matching every existing index migration in this repo.)

CREATE INDEX IF NOT EXISTS entries_run_observations_run_channel_recorded_idx
    ON entries_run_observations (run_id, channel_name, recorded_at DESC);

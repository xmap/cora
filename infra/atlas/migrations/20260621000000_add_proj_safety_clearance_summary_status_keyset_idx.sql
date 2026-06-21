-- atlas:txmode none
-- Add the (status, registered_at, clearance_id) composite index to
-- proj_safety_clearance_summary.
--
-- The init migration (20260516000000) deferred per-filter indexes "until a
-- slow-query incident surfaces". ClearanceWatcher (cora.api._clearance_watcher)
-- is the first recurring status-filtered consumer: each tick it drains
-- list_clearances for status in (Submitted, UnderReview, Approved), i.e.
-- WHERE status = $1 ORDER BY registered_at, clearance_id. This composite makes
-- that scan status-selective and index-orders the keyset, instead of scanning
-- the (registered_at, clearance_id) keyset index and post-filtering status.
-- Additive + forward-only.

CREATE INDEX IF NOT EXISTS proj_safety_clearance_summary_status_keyset_idx
    ON proj_safety_clearance_summary (status, registered_at, clearance_id);

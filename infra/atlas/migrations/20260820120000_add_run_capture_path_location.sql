-- Re-key run_capture_path so one Run can hold one observed path PER
-- STORAGE LOCATION, not one path outright.
--
-- Why now: the next slice registers a second Distribution once a scan's
-- bytes reach APS Data Management. That is a second real path for the
-- same Run (/gdata/dm/2BM/<yyyy-mm>/<exp>/data/<file>.h5 alongside
-- /local1/2BM/<exp>/<file>.h5), carrying the same PI surname, so it
-- needs the same vaulting. Under the old run_id PRIMARY KEY, writing it
-- would have overwritten the acquisition path in place via
-- ON CONFLICT (run_id) DO UPDATE, and every cora-capture-path:// locator
-- minted against that path would have stopped resolving, silently, with
-- no event recording that it happened. Nothing writes a second path yet,
-- so this closes a trap laid in the next slice's path rather than a live
-- defect, and it is cheapest now: the ingest sweep that mints those
-- locators is still switched off.
--
-- Schema decisions:
--   - host + root are NULLABLE, because rows written before this
--     migration genuinely have no recorded location. NULL here means
--     "observed before CORA tracked location", which is true, rather
--     than a sentinel string that would assert a location nobody
--     measured. Rows written after this migration carry both, except
--     when the observed path matched no configured root at all (the
--     same condition under which mint_capture_path_locator refuses).
--   - UNIQUE NULLS NOT DISTINCT (PG15+, deployed on PG18) is what makes
--     nullable location columns workable as the upsert conflict target:
--     the default NULLS DISTINCT would treat every legacy row as unique
--     against itself and break ON CONFLICT re-observation. With NULLS
--     NOT DISTINCT a legacy row stays exactly one row per run_id.
--   - The surrogate capture_path_id PRIMARY KEY is forced by the above,
--     not chosen for taste: a PRIMARY KEY cannot span nullable columns,
--     so (run_id, host, root) cannot be the PK while host/root are
--     nullable. It also gives a future erasure slice a stable handle.
--   - root is recorded as observed, NOT as a reference to current
--     configuration. A deployment that later repoints
--     scan_probe_allowed_roots does not orphan these rows: resolution
--     matches the root embedded in the locator at mint time, which is
--     equally historical, so both sides move together. Config changes
--     affect only newly minted locators, which is correct.
--   - capture_path_id DEFAULTs to gen_random_uuid() rather than being
--     supplied by the application. A surrogate key carries no meaning a
--     writer could get right or wrong, so requiring every INSERT to
--     invent one is pure ceremony that any raw-SQL writer (test
--     fixtures, a future backfill) would forget. The default makes the
--     column invisible to everything that does not care about it.
--   - No forgotten_at / soft-delete column, mirroring the init
--     migration: the tombstone would itself be identifying.
--
-- Forward-only per project_forward_only_migrations: rollback is a new
-- compensating migration, never an edit here.

ALTER TABLE run_capture_path
    ADD COLUMN capture_path_id UUID,
    ADD COLUMN host            TEXT CHECK (length(host) BETWEEN 1 AND 255),
    ADD COLUMN root            TEXT CHECK (length(root) BETWEEN 1 AND 511);

UPDATE run_capture_path
    SET capture_path_id = gen_random_uuid()
    WHERE capture_path_id IS NULL;

ALTER TABLE run_capture_path
    ALTER COLUMN capture_path_id SET NOT NULL,
    ALTER COLUMN capture_path_id SET DEFAULT gen_random_uuid();

ALTER TABLE run_capture_path
    DROP CONSTRAINT run_capture_path_pkey;

ALTER TABLE run_capture_path
    ADD CONSTRAINT run_capture_path_pkey PRIMARY KEY (capture_path_id);

CREATE UNIQUE INDEX run_capture_path_run_location_key
    ON run_capture_path (run_id, host, root) NULLS NOT DISTINCT;

-- load_run_capture_path resolves the MOST RECENTLY OBSERVED row for a
-- run_id across every location, so the display read is an ordered scan
-- of one run's rows rather than a point lookup.
CREATE INDEX run_capture_path_run_observed_at_idx
    ON run_capture_path (run_id, observed_at DESC);

COMMENT ON COLUMN run_capture_path.capture_path_id IS
    'Surrogate primary key. Forced by host/root being nullable: a PRIMARY KEY cannot span nullable columns. A future erasure slice must still delete by run_id across ALL of a runs locations, never by this id alone: erasing one location and leaving a sibling row keeps the surname on disk.';
COMMENT ON COLUMN run_capture_path.host IS
    'Host the path was observed on, as recorded at observation time (never a reference to current settings). NULL means the row predates location tracking, or the observed path matched no configured root.';
COMMENT ON COLUMN run_capture_path.root IS
    'Facility-level storage tier the observed path fell under, recorded verbatim at observation time. Must be the tier (/local1/2BM), never a path that itself contains personal data; see mint_capture_path_locator''s docstring for why that distinction is load-bearing.';
COMMENT ON COLUMN run_capture_path.run_id IS
    'Matches Run aggregate stream_id. One row per (Run, storage location) rather than one row per Run: a scan file observed on both the acquisition tier and the archive tier is two rows.';

-- Record the eight scan-configuration ENUM PVs (ScanType, FlatFieldMode,
-- DarkFieldMode, FlatFieldAxis, ReturnRotation, DifferentFlatExposure,
-- SampleOutAngleEnable, FlipStitch) that `ControlPort` already decodes
-- as `Measurement(kind="Categorical")` but
-- `entries_run_observations` cannot carry: `value` was `double precision
-- NOT NULL`, so a categorical baseline reading had nowhere to land. This
-- is a parity gap, not a preference: a CONDUCTED Run's Method/Plan
-- declares scan configuration by construction; a WITNESSED Run can only
-- read what the substrate exposes, and today it cannot even read these
-- eight.
--
-- Design: ONE table (Option A), not a sibling entries table. The
-- exporter's reader is `SELECT * FROM {table}`
-- (record_export/_registry.py), so a new column here is exported for
-- free with no registry edit, no new logbook kind, and no envelope
-- decision. A genesis snapshot with both numeric and categorical
-- readings stays one row set behind one `sampling_procedure="baseline"`
-- query, per project_record_is_two_tier.md's "one retrievable snapshot"
-- requirement.
--
-- `value` becomes nullable and `categorical_value` is added, with a
-- CHECK enforcing exactly one of the two is ever set. Named
-- `..._value_exclusive_arc`, matching the exactly-one-of naming already
-- established at `proj_federation_permit_summary_terms_exclusive_arc`
-- (20260530210000_init_proj_federation_permit_summary.sql) rather than
-- naming the `<>` operator used to express it. This is NOT the
-- `value: float | str` union that was explicitly rejected: numeric
-- observations keep their own typed, sortable, range-queryable column
-- untouched by this change.
--
-- The categorical value carries the enum LABEL as EPICS resolves it
-- ('Fly', 'Both', 'No'), never an index: the facility's own vocabulary,
-- not a CORA-invented enum, so an unrecognized label is data, not an
-- error, and there is deliberately no CHECK-constrained value set here.
--
-- Live-schema check (docker exec cora-postgres psql ... \d
-- entries_run_observations) confirms the table's check constraints still
-- carry the PRE-RENAME name: the 2026-06-10
-- entries_run_readings -> entries_run_observations rename
-- (20260610020000_rename_entries_run_readings_to_entries_run_observations.sql)
-- renamed the table and its indexes but not its CHECK constraints, so
-- the value constraint being replaced here is
-- `entries_run_readings_value_check`, not an `entries_run_observations_*`
-- name. Not fixing that pre-existing inconsistency here (out of scope,
-- untouched constraints stay untouched); only the constraint this
-- migration actually replaces gets the current table's name.

ALTER TABLE entries_run_observations
    ALTER COLUMN value DROP NOT NULL;

ALTER TABLE entries_run_observations
    DROP CONSTRAINT entries_run_readings_value_check;

ALTER TABLE entries_run_observations
    ADD CONSTRAINT entries_run_observations_value_check CHECK (
        value IS NULL OR (
            value = value
            AND value <> 'Infinity'::double precision
            AND value <> '-Infinity'::double precision
        )
    );

-- 64 chars mirrors `units`' own bound (entries_run_readings_units_check):
-- a generous, round ceiling for a short substrate string, not a
-- tightly-fitted EPICS-spec number.
ALTER TABLE entries_run_observations
    ADD COLUMN categorical_value text
        CHECK (categorical_value IS NULL OR length(categorical_value) BETWEEN 1 AND 64);

ALTER TABLE entries_run_observations
    ADD CONSTRAINT entries_run_observations_value_exclusive_arc
        CHECK ((value IS NOT NULL) <> (categorical_value IS NOT NULL));

-- Equipment BC: Role summary read model (Layer 3 sub-slice 3A of
-- [[project-role-aggregate-design]]).
--
-- Folds the Role aggregate's RoleDefined event into the
-- `proj_equipment_role_summary` read model used by Layer-3 cross-BC
-- consumers (3B Family.presents_as validation, 3C Assembly.presents_as
-- validation, 3D bind_plan_role satisfaction check, 3E
-- Capability.suggested_roles existence check) and by future operator-
-- facing list / get endpoints.
--
-- ## What ships in 3A
--
-- Per Q1 user pick (2026-06-10): RoleDefined event only. The
-- RoleAffordancesUpdated / RoleSignalsUpdated events are deferred
-- until the Lock 14 SiLA-2 FQN-terminal-major versioning trigger
-- fires. This migration creates the columns that future update events
-- will populate (TEXT[] for affordances and signal vocabularies, name
-- + docstring TEXT) so the next migration is an UPDATE rule add at
-- the projection-writer level, not a column add.
--
-- ## Structural invariants enforced at the DB tier
--
--   - role_id PK is the natural key (one row per Role).
--   - name is NOT NULL and 1-200 chars (CHECK enforces non-empty;
--     the application-side `RoleName` VO enforces the upper bound).
--   - docstring is NOT NULL and 1-2000 chars (CHECK enforces
--     non-empty; application-side `InvalidRoleDocstringError`
--     enforces the upper bound).
--   - required_affordances and optional_affordances are TEXT[]
--     defaulting to empty array. Disjointness is enforced at the
--     decider, not the DB (would require a CHECK with an array
--     operator; deferred).
--   - produces and consumes are TEXT[] defaulting to empty array.
--   - created_at is the canonical keyset-pagination key paired with
--     role_id; future list endpoint cursors use it.
--
-- ## Mutable read model
--
-- cora_app gets full DML. Rebuildable from events. Projection name
-- `proj_equipment_role_summary` matches the table name + the
-- bookmark row + `RoleSummaryProjection.name`.

CREATE TABLE proj_equipment_role_summary (
    role_id                UUID         PRIMARY KEY,
    name                   TEXT         NOT NULL CHECK (
        length(name) > 0
    ),
    docstring              TEXT         NOT NULL CHECK (
        length(docstring) > 0
    ),
    required_affordances   TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
    optional_affordances   TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
    produces               TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
    consumes               TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
    created_at             TIMESTAMPTZ  NOT NULL,
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE proj_equipment_role_summary IS
    'Equipment BC Role summary read model. Lightweight global functional binding contract (Imager, Positioner, Controller, Detector) above the per-Method positional RoleRequirement pattern; consumed by Layer-3 cross-aggregate satisfaction checks. No FSM at 3A per Lock 14 deferral.';
COMMENT ON COLUMN proj_equipment_role_summary.required_affordances IS
    'Affordance value strings every satisfying Family MUST advertise. Decider enforces disjointness with optional_affordances.';
COMMENT ON COLUMN proj_equipment_role_summary.optional_affordances IS
    'Affordance value strings a satisfying Family MAY advertise. Informative at 3A; consumer gates on it independently when meaningful.';
COMMENT ON COLUMN proj_equipment_role_summary.produces IS
    'Open SignalType vocabulary satisfying Assets emit (out-direction port signal_type). Informative at 3A; Layer-4 wire-guidance may gate on it.';
COMMENT ON COLUMN proj_equipment_role_summary.consumes IS
    'Open SignalType vocabulary satisfying Assets accept (in-direction port signal_type). Informative at 3A.';

CREATE UNIQUE INDEX proj_equipment_role_summary_name_lower_uq
    ON proj_equipment_role_summary (LOWER(name));

CREATE INDEX proj_equipment_role_summary_keyset_idx
    ON proj_equipment_role_summary (created_at, role_id);

GRANT SELECT, INSERT, UPDATE, DELETE
    ON proj_equipment_role_summary TO cora_app;

INSERT INTO projection_bookmarks (name)
VALUES ('proj_equipment_role_summary')
ON CONFLICT DO NOTHING;

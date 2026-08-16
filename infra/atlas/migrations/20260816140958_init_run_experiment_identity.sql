-- Slice 14a (memory/project_witnessed_run_prelive_slices.md): vault for
-- a witnessed Run's proposal / ESAF / ESAF-DOI experiment identity.
--
-- These three PVs (`ProposalNumber`, `ESAFNumber`, `ESAFDOINumber` under
-- `2bmb:TomoScan:`) are stamped by dmagic from APS scheduling data, not
-- by the IOC, and RunWitness has no operator to ask for a proposal the
-- way start_run's operator-supplied external_refs does. Auto-harvesting
-- them onto RunStarted would put an unerasable, re-identifying fact
-- (D0: a proposal number plus a timestamp is a strong join key against
-- public APS scheduling data) into an immutable, INSERT-only event.
-- ESAFDOINumber was checked and is populated from an internal,
-- authenticated APS API (EsafApsDbApi), not a DOI registration agency;
-- unconfirmed as a genuinely resolvable public identifier, so it vaults
-- alongside the other two rather than riding an event as its own scheme.
--
-- A SIBLING table to run_capture_path, not a generalization of it: a
-- capture path and a proposal/ESAF number are different kinds of fact
-- (see experiment_identity.py's own module docstring for the full
-- argument). Same PII-vault-shaped posture and write-once-at-promotion
-- timing, for a different reason.
--
-- Schema decisions (mirroring run_capture_path's init migration):
--   - run_id is both PK and (application-level) link to the Run
--     aggregate's stream_id. No SQL FK to events.stream_id because the
--     events table is INSERT-only at the role level per
--     project_immutability_guarantee; FK enforcement is application
--     discipline.
--   - Each of proposal_number / esaf_number / esaf_doi_number is independently
--     NULLABLE, paired with its own *_observed_at (the substrate's own
--     reading time, never CORA's clock): a deployment may configure
--     fewer than three roles, or the substrate may report "Unknown" /
--     empty for one PV while another reads a real value. CORA's own
--     reader treats "Unknown" and empty as absent and never writes them
--     here (see cora.api._capture_experiment_identity_reader); this
--     table's NULL is the "absent" state, not the substrate's literal.
--   - CHECK bounds are defense-in-depth (a NULL value passes a CHECK
--     unconditionally in Postgres, so these do not force presence):
--     200 chars for proposal_number / esaf_number (matches
--     shared.identifier.IDENTIFIER_VALUE_MAX_LENGTH's bound for a
--     comparable free-form identifier value), 500 for esaf_doi_number (a DOI
--     suffix can run longer than a bare proposal/ESAF number).
--   - No forgotten_at / soft-delete column, mirroring run_capture_path:
--     it would itself be identifying ("this Run's proposal existed and
--     was erased on Y").
--   - created_at is application-supplied (the promotion's own clock
--     read). updated_at defaults to now() for a future rename/rewrite
--     path.
--
-- RLS posture (defense-in-depth, mirroring run_capture_path exactly):
--   - ENABLE + FORCE ROW LEVEL SECURITY.
--   - Two flat permissive policies for cora_app (read + write), both
--     USING (true) for v1, cora_app being the only runtime role.
--
-- No erasure slice ships in this commit (rule-of-three; nothing calls
-- DELETE yet), but DELETE is granted now so a future forget-style slice
-- needs no follow-up grant migration.

CREATE TABLE run_experiment_identity (
    run_id                       UUID        PRIMARY KEY,
    proposal_number              TEXT        CHECK (length(proposal_number) BETWEEN 1 AND 200),
    proposal_number_observed_at  TIMESTAMPTZ,
    esaf_number                  TEXT        CHECK (length(esaf_number) BETWEEN 1 AND 200),
    esaf_number_observed_at      TIMESTAMPTZ,
    esaf_doi_number              TEXT        CHECK (length(esaf_doi_number) BETWEEN 1 AND 500),
    esaf_doi_number_observed_at  TIMESTAMPTZ,
    created_at                   TIMESTAMPTZ NOT NULL,
    updated_at                   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE run_experiment_identity IS
    'Vault for a witnessed Run''s proposal/ESAF/ESAF-DOI experiment identity (memory/project_witnessed_run_prelive_slices.md, slice 14a). Mutable. No SQL FK to events (INSERT-only role); run_id matches the Run aggregate stream_id by application discipline.';
COMMENT ON COLUMN run_experiment_identity.run_id IS
    'Matches Run aggregate stream_id. One row per witnessed Run that has at least one resolved experiment-identity value.';
COMMENT ON COLUMN run_experiment_identity.proposal_number IS
    'The APS beamtime proposal number read from 2bmb:TomoScan:ProposalNumber. Never on an event: auto-harvested with no operator gesture behind it, and re-identifying alongside a timestamp against public APS scheduling data (D0).';
COMMENT ON COLUMN run_experiment_identity.proposal_number_observed_at IS
    'The substrate''s own timestamp for this reading (Measurement.produced_at), not CORA''s clock. dmagic writes this PV from APS scheduling and it persists across beamtimes until overwritten; this column is the only staleness evidence available.';
COMMENT ON COLUMN run_experiment_identity.esaf_number IS
    'The ESAF (Experiment Safety Assessment Form) number read from 2bmb:TomoScan:ESAFNumber. Same posture as proposal_number.';
COMMENT ON COLUMN run_experiment_identity.esaf_number_observed_at IS
    'The substrate''s own timestamp for this reading; see proposal_number_observed_at.';
COMMENT ON COLUMN run_experiment_identity.esaf_doi_number IS
    'The value read from 2bmb:TomoScan:ESAFDOINumber. Not confirmed as a publicly resolvable DOI (the upstream dmagic source reads it from an internal, authenticated APS API, not a DOI registry); vaulted alongside the other two rather than treated as a public identifier.';
COMMENT ON COLUMN run_experiment_identity.esaf_doi_number_observed_at IS
    'The substrate''s own timestamp for this reading; see proposal_number_observed_at.';

-- Mutable PII-vault-shaped table: cora_app gets full CRUD. DELETE is the
-- future erasure mechanism; UPDATE lets a later slice correct/rewrite a row.
GRANT SELECT, INSERT, UPDATE, DELETE ON run_experiment_identity TO cora_app;

-- Row-Level Security: defense-in-depth.
ALTER TABLE run_experiment_identity ENABLE ROW LEVEL SECURITY;
ALTER TABLE run_experiment_identity FORCE  ROW LEVEL SECURITY;

CREATE POLICY run_experiment_identity_cora_app_read
    ON run_experiment_identity FOR SELECT
    TO cora_app
    USING (true);

CREATE POLICY run_experiment_identity_cora_app_write
    ON run_experiment_identity FOR ALL
    TO cora_app
    USING (true)
    WITH CHECK (true);

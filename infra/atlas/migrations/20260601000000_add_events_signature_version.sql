-- Add signature_version column to the events table.
--
-- Iter-b Stage 3b of the federation port-tier work
-- (project_canonicalization_port_design.md + project_federation_port_design.md):
-- the verifier dispatches to the matching SigningPort adapter via the
-- SigningRegistry keyed on signature_version. Today the only registered
-- recipe is "cora/v1" (Ed25519 over DSSE-PAE bytes); future wire-tier
-- adapters (DSSE+Sigstore, COSE_Sign1+SCITT) will register additional
-- versions alongside without invalidating v1 per the
-- "v1 NEVER deprecated" invariant.
--
-- Why nullable and undefaulted:
--
--   - signature_version IS NULL is the legitimate marker for
--     pre-rollout events (immortal per project_immutability_guarantee)
--     and for unsigned events of any kind. Forward-only migration
--     policy forbids backfill; historical rows stay with NULL forever
--     and that is the correct semantic.
--   - Matches the existing nullable shape of `signature` and
--     `signature_kid` columns added in
--     20260523214753_add_events_signature_columns.sql.
--
-- The CHECK constraint enforces the matched-pair invariant: a
-- signature_version without a signature (or vice versa) is a write-
-- side bug the database catches at INSERT, before the row lands.
-- Distinct from "no signature at all" (all three NULL) which is
-- legitimate per the design lock.
--
-- text for signature_version:
--
--   The version identifier is namespaced like "cora/v1" or
--   "cora/v2-cose"; the namespace prefix permits facility-specific
--   extensions ("aps/v1-internal") without colliding with CORA-
--   shipped adapter ids. Length is bounded but variable; text is
--   the unconstrained choice.
--
-- No index:
--
--   Verification is per-row; the verifier resolves the SigningPort
--   from the registry by exact-match string lookup. No "find all
--   events signed under version X" filter query in the design.
--
-- Length constraint (defense-in-depth):
--
--   1 to 64 chars when non-NULL. 64 accommodates
--   "<vendor-prefix>/<version>-<recipe-variant>" namespaced
--   identifiers with headroom; bigger values are almost certainly
--   a misuse of the field for unrelated metadata.

ALTER TABLE events
    ADD COLUMN signature_version TEXT;

ALTER TABLE events
    ADD CONSTRAINT events_signature_version_consistency
        CHECK ((signature IS NULL) = (signature_version IS NULL)),
    ADD CONSTRAINT events_signature_version_length
        CHECK (signature_version IS NULL OR octet_length(signature_version) BETWEEN 1 AND 64);

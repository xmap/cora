-- Fixes a latent permission gap: five entries_* tables were created
-- with a header comment claiming cora_app "gets SELECT + INSERT via
-- ALTER DEFAULT PRIVILEGES in 20260512230000_init_role_cora_app.sql".
-- That claim is false. The role-init migration's
-- `ALTER DEFAULT PRIVILEGES ... GRANT USAGE, SELECT ON SEQUENCES`
-- covers SEQUENCES only, never TABLES, so cora_app has never had a
-- working grant on any of these tables. Confirmed by grepping every
-- migration for a GRANT naming each table plus cora_app: none exists.
--
-- Affected tables, named by their CURRENT identifier (two of the five
-- were renamed after creation, so the GRANT below must target the name
-- the table actually holds by this point in migration history, not the
-- name it was created under):
--   entries_run_readings              -> entries_run_observations
--     (20260610020000_rename_entries_run_readings_to_entries_run_observations.sql)
--   entries_operation_procedure_steps -> entries_operation_procedure_activities
--     (20260610030000_rename_entries_operation_procedure_steps_to_entries_operation_procedure_activities.sql)
--   entries_run_feed_heartbeats               (unrenamed)
--   entries_operation_procedure_diagnostics   (unrenamed)
--   entries_operation_procedure_outcomes      (unrenamed)
--
-- Each already carries its own REVOKE UPDATE, DELETE, TRUNCATE (a
-- privilege revocation attaches to the table object and survives a
-- later rename), so only the missing GRANT is added here.
--
-- Purely additive and non-destructive: a GRANT cannot lock a table or
-- fail against existing rows. Currently dormant, not live, because the
-- pilot's DATABASE_URL still connects as the owner role (cora), not
-- cora_app; this closes the gap before anything switches to the
-- restricted role. See tests/architecture/test_entries_table_grants.py,
-- whose _GRANDFATHERED allowlist these five names are removed from in
-- the same change as this migration.

GRANT SELECT, INSERT ON entries_run_observations TO cora_app;
GRANT SELECT, INSERT ON entries_operation_procedure_activities TO cora_app;
GRANT SELECT, INSERT ON entries_run_feed_heartbeats TO cora_app;
GRANT SELECT, INSERT ON entries_operation_procedure_diagnostics TO cora_app;
GRANT SELECT, INSERT ON entries_operation_procedure_outcomes TO cora_app;

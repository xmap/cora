-- Widen proj_equipment_asset_summary with the partition_rule_kind denormalized
-- indicator: a nullable TEXT column capturing the PartitionRuleKind discriminator
-- of the Asset's partition rule. Supports the PseudoAxis Family pattern via the
-- update_asset_partition_rule slice.
--
-- Per Lock 2 and Lock 9 of project_pseudoaxis_design (v3, design lock):
--
--   - partition_rule_kind is NULL for non-PseudoAxis Assets.
--   - partition_rule_kind is NULL for PseudoAxis Assets whose partition rule
--     has not yet been set (additive-state pattern; the projection writer
--     leaves it NULL until the first AssetPartitionRuleUpdated event lands).
--   - partition_rule_kind is one of {Affine, Aggregation, LookupTable,
--     CompositePartition, SolverReference} when the rule is set (the 5 closed
--     PartitionRuleKind discriminator values per Lock 2).
--   - The CHECK constraint is a named constraint so a future migration that
--     adds a new PartitionRuleKind value can DROP CONSTRAINT + ADD CONSTRAINT
--     cleanly, following the closed-catalog growth rule (Lock 2).
--
-- ## Why denormalization
--
-- The Asset summary projection is the read-model interface for asset queries
-- and views. The partition_rule_kind column enables future query filters
-- (e.g., "list all Assets with partition_rule_kind = 'Affine'") and
-- observation without a costly join or embedded JSON extraction.
--
-- ## Forward-only
--
-- Pure ADD COLUMN with safe NULL defaults; greenfield-friendly; no backfill
-- needed (projections rebuild from the event store and pick up
-- partition_rule_kind from AssetPartitionRuleUpdated event replay). Rollback
-- via a NEW compensating migration per project_forward_only_migrations.
--
-- ## Closed-catalog growth rule
--
-- When a new PartitionRuleKind shape ships in a future stage, the migration
-- that adds it will:
--   1. DROP CONSTRAINT proj_equipment_asset_summary_partition_rule_kind_check;
--   2. ADD CONSTRAINT proj_equipment_asset_summary_partition_rule_kind_check
--      CHECK (partition_rule_kind IS NULL OR partition_rule_kind IN
--        ('Affine', 'Aggregation', 'LookupTable', 'CompositePartition',
--         'SolverReference', '<NewKind>'))
--
-- This preserves the invariant without requiring a separate migration.

ALTER TABLE proj_equipment_asset_summary
    ADD COLUMN partition_rule_kind TEXT NULL;

ALTER TABLE proj_equipment_asset_summary
    ADD CONSTRAINT proj_equipment_asset_summary_partition_rule_kind_check
    CHECK (partition_rule_kind IS NULL OR partition_rule_kind IN
        ('Affine', 'Aggregation', 'LookupTable', 'CompositePartition',
         'SolverReference'));

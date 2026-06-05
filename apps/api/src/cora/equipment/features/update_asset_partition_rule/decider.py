"""Pure decider for the `UpdateAssetPartitionRule` command.

The decider:
  - Raises AssetNotFoundError on empty state
  - Raises AssetCannotUpdatePartitionRuleError if the Asset's
    lifecycle is Decommissioned (immutable once retired)
  - Trusts that the PartitionRule shape has already passed
    Pydantic validation at the route boundary; shape-level
    invariants (NaN/Inf guards, monotonicity checks, etc.) are
    validated during VO construction and do not re-run here
  - Self-reference and nesting checks are currently structural no-ops
    at the decider tier (current PartitionRule shapes do NOT carry
    constituent_asset_ids directly; they are inferred from Asset.ports
    at runtime-evaluator time). The handler tier is responsible for
    cross-aggregate validation (Asset-of-Family-PseudoAxis,
    constituent-existence, constituent-Family-membership) per the
    cross-aggregate-validating-create pattern; the decider stays pure
    and operates only on what is on Asset state itself
  - No-ops (returns []) if the new rule equals the current rule
    (idempotent re-submission, no audit value)
  - Otherwise emits AssetPartitionRuleUpdated(asset_id, partition_rule,
    occurred_at) with the command's partition_rule payload (None clears)

Both genesis and mutation flow through the same event. Genesis detection
(was-the-prior-rule-None) is reconstructable from the event stream by
replay: the first AssetPartitionRuleUpdated event on a stream with
non-None partition_rule is the genesis. Mirrors AssetSettingsUpdated
precedent (one event covers set + update + clear).

The handler is responsible for:
  1. Loading the Asset's Family membership to verify it is PseudoAxis
  2. If the rule is non-None, loading each constituent_asset_id (if the
     rule shape carries them) to verify they exist and are not themselves
     of Family PseudoAxis (nesting prevention)
  3. If the rule is a LookupTable, loading the Calibration revision to
     verify it exists and is not retracted

The decider stays pure: no I/O, no aggregate boundary crossing.
"""

from datetime import datetime

from cora.equipment.aggregates.asset import (
    Asset,
    AssetCannotUpdatePartitionRuleError,
    AssetLifecycle,
    AssetNotFoundError,
    AssetPartitionRuleUpdated,
)
from cora.equipment.features.update_asset_partition_rule.command import (
    UpdateAssetPartitionRule,
)


def decide(
    state: Asset | None,
    command: UpdateAssetPartitionRule,
    *,
    now: datetime,
) -> list[AssetPartitionRuleUpdated]:
    """Decide the events produced by an Asset.partition_rule update.

    Invariants:
      - State must not be None -> AssetNotFoundError
      - Asset.lifecycle must not be Decommissioned
        -> AssetCannotUpdatePartitionRuleError
      - No re-emission if the new rule equals the current rule
        (idempotent re-submission carries no audit value)

    Self-reference and nesting checks are structural no-ops at this tier
    (current PartitionRule shapes carry no constituent_asset_ids directly).
    The handler enforces cross-aggregate invariants (Family membership,
    constituent existence, nesting prevention) per the cross-aggregate-
    validating-create pattern.
    """
    if state is None:
        raise AssetNotFoundError(command.asset_id)

    if state.lifecycle == AssetLifecycle.DECOMMISSIONED:
        raise AssetCannotUpdatePartitionRuleError(
            command.asset_id,
            "Asset is Decommissioned (immutable once retired)",
        )

    # Idempotent re-submission: no audit value if the rule is unchanged.
    if command.partition_rule == state.partition_rule:
        return []

    return [
        AssetPartitionRuleUpdated(
            asset_id=state.id,
            partition_rule=command.partition_rule,
            occurred_at=now,
        )
    ]

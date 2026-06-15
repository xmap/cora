"""Pure decider for the `UpdateAssetPartitionRule` command.

The decider:
  - Raises AssetNotFoundError on empty state
  - Raises AssetCannotUpdatePartitionRuleError if the Asset's
    lifecycle is Decommissioned (immutable once retired)
  - Trusts that the PartitionRule shape has already passed
    Pydantic validation at the route boundary; finite-value
    invariants (NaN/Inf guards) are validated during VO
    construction. A LookupTable's invertible=True monotonicity is
    NOT machine-checked (the calibration revision is not loaded
    here); it is a caller assertion, see LookupTable in
    `_partition_rule.py`
  - Self-reference and nesting checks are currently structural no-ops
    at the decider tier (current PartitionRule shapes do NOT carry
    constituent_asset_ids directly; they are inferred from Asset.ports
    at runtime-evaluator time)
  - No-ops (returns []) if the new rule equals the current rule
    (idempotent re-submission, no audit value)
  - Otherwise emits AssetPartitionRuleUpdated(asset_id, partition_rule,
    occurred_at) with the command's partition_rule payload (None clears)

Both genesis and mutation flow through the same event. Genesis detection
(was-the-prior-rule-None) is reconstructable from the event stream by
replay: the first AssetPartitionRuleUpdated event on a stream with
non-None partition_rule is the genesis. Mirrors AssetSettingsUpdated
precedent (one event covers set + update + clear).

The slice is self-gating on `Asset.partition_rule` presence: any
Asset that has had a rule set (or is being given one) is a virtual
axis. The earlier Family-membership gate is removed, see the
[[project_pseudoaxis_design]] supersession note.

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

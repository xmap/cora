"""Vertical slice for the `UpdateAssetPartitionRule` command.

Module-as-namespace surface:

    from cora.equipment.features import update_asset_partition_rule

    cmd = update_asset_partition_rule.UpdateAssetPartitionRule(
        asset_id=..., partition_rule=...
    )
    handler = update_asset_partition_rule.bind(deps)
    await handler(cmd, principal_id=..., correlation_id=...)

The slice that sets, updates, or clears a PseudoAxis Asset's
`partition_rule` field. Payload carries `PartitionRule | None`,
where None clears the rule. Single event `AssetPartitionRuleUpdated`
covers all three transitions (genesis, mutation, clearing), mirroring
the `AssetSettingsUpdated` precedent. The route layer converts JSON
body to the frozen-dataclass union before invoking the handler.
"""

from cora.equipment.features.update_asset_partition_rule import tool
from cora.equipment.features.update_asset_partition_rule.command import (
    UpdateAssetPartitionRule,
)
from cora.equipment.features.update_asset_partition_rule.decider import decide
from cora.equipment.features.update_asset_partition_rule.handler import Handler, bind
from cora.equipment.features.update_asset_partition_rule.route import router

__all__ = [
    "Handler",
    "UpdateAssetPartitionRule",
    "bind",
    "decide",
    "router",
    "tool",
]

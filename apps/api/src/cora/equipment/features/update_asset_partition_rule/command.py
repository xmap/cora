"""The `UpdateAssetPartitionRule` command: intent dataclass for this slice.

`asset_id` is the target Asset aggregate (must be of Family PseudoAxis and
not Decommissioned). `partition_rule` is the typed VO to assign, or None to
clear the existing rule. The domain decider validates Family membership,
lifecycle, self-reference, nesting, and Calibration revision availability.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.equipment.aggregates._partition_rule import PartitionRule


@dataclass(frozen=True)
class UpdateAssetPartitionRule:
    """Update a PseudoAxis Asset's partition rule, or clear it via None.

    The partition_rule field accepts a typed PartitionRule VO (one of
    Affine, Aggregation, LookupTable, CompositePartition, SolverReference)
    or None to clear the rule. Route-layer Pydantic parsing converts JSON
    discriminated-union syntax to the frozen-dataclass union; the decider
    enforces domain invariants (Family membership, non-Decommissioned,
    self-reference prevention, nesting prevention, Calibration revision
    availability for LookupTable shapes).

    Mirrors the UpdateAssetSettings precedent: one slice, one event
    (AssetPartitionRuleUpdated), covers genesis + mutation + removal via
    PartitionRule | None semantics.
    """

    asset_id: UUID
    partition_rule: PartitionRule | None

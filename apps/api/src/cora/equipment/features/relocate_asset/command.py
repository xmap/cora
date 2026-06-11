"""The `RelocateAsset` command — intent dataclass for this slice.

Hierarchy mutation, not a lifecycle transition. The asset stays
in its current lifecycle state; only `parent_id` changes.

The command supplies only the **target** parent (and a reason);
the decider reads the **source** parent from the loaded state and
emits an `AssetRelocated` event carrying both. This keeps the
caller-side API tight (no need to assert current parent) while
the audit log still records both sides.

`to_parent_id` is `UUID` (non-null in the type) — root Assets
(parent_id=None) cannot relocate per the decider's anchoring
guard, so there's no scenario where you'd "relocate to
no-parent". `reason` is operator-supplied free text (validated at
the API boundary, not by a domain VO).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RelocateAsset:
    """Move an existing asset under a new parent in the hierarchy."""

    asset_id: UUID
    to_parent_id: UUID
    reason: str

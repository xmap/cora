"""The `DecommissionAsset` command — intent dataclass for this slice.

`asset_id` is the **target** Asset aggregate (the asset being
retired). The principal-id of the invoker is supplied separately by
the application handler at call time. Mirrors `ActivateAsset` /
`RemoveSubject`.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DecommissionAsset:
    """Decommission an existing asset, retiring it from service."""

    asset_id: UUID
    reason: str

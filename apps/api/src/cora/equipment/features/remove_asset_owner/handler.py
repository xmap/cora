"""Application handler for the `remove_asset_owner` slice.

Mirror of `add_asset_owner.handler`. Update-style handler; the
canonical body lives in `make_asset_update_handler`.

Not idempotency-wrapped: removal is strict-not-idempotent at the
decider (second remove hits `AssetOwnerNotPresentError`).
"""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.remove_asset_owner.command import RemoveAssetOwner
from cora.equipment.features.remove_asset_owner.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every remove_asset_owner handler implements."""

    async def __call__(
        self,
        command: RemoveAssetOwner,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a remove_asset_owner handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="RemoveAssetOwner",
        log_prefix="remove_asset_owner",
        decide_fn=decide,
    )

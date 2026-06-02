"""Application handler for the `remove_asset_alternate_identifier` slice."""

from typing import Protocol
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.features.remove_asset_alternate_identifier.command import (
    RemoveAssetAlternateIdentifier,
)
from cora.equipment.features.remove_asset_alternate_identifier.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID


class Handler(Protocol):
    """Callable interface every remove_asset_alternate_identifier handler implements."""

    async def __call__(
        self,
        command: RemoveAssetAlternateIdentifier,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a remove_asset_alternate_identifier handler closed over the shared deps."""
    return make_asset_update_handler(
        deps,
        command_name="RemoveAssetAlternateIdentifier",
        log_prefix="remove_asset_alternate_identifier",
        decide_fn=decide,
    )

"""Application handler for the `assign_asset_persistent_id` slice.

Server-mint posture (Lock 12): the route forwards `(asset_id, scheme,
suffix)` to the handler, and the handler closure resolves the
`PersistentIdentifier` from the `DoiMinter` port BEFORE invoking the
pure decider. Non-determinism (the minter call) is captured in the
handler closure per [[project-non-determinism-principle]], NOT at the
route layer. One minter call site (this handler), not two (route + MCP
tool).

Returns the assigned `PersistentIdentifier` so the route layer can
echo it in the 201 response body (Lock 17): the operator needs the
authority-minted DOI string immediately; reading back through
`GET /assets/{id}/pidinst` is a wasteful round-trip and is subject to
projection lag.

NOT idempotency-wrapped at the CORA layer (Lock 13): set-once at the
decider PLUS DOI-string-as-dedup-key at DataCite (F5.2 PUT /dois/{id}
upsert semantics) covers retry safely without a CORA idempotency_key.

Mint failures bubble as `PersistentIdentifierMintError` from the port
(raised by the production adapter); the route layer maps it to HTTP
502 via the standard exception-handler registration in
`equipment/routes.py`.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from cora.equipment._asset_update_handler import make_asset_update_handler
from cora.equipment.aggregates.asset import (
    Asset,
    AssetEvent,
)
from cora.equipment.features.assign_asset_persistent_id.command import AssignAssetPersistentId
from cora.equipment.features.assign_asset_persistent_id.decider import decide
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identifier import PersistentIdentifier

if TYPE_CHECKING:
    from cora.equipment.ports.doi_minter import DoiMinter


class Handler(Protocol):
    """Callable interface every assign_asset_persistent_id handler implements."""

    async def __call__(
        self,
        command: AssignAssetPersistentId,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PersistentIdentifier: ...


def bind(deps: Kernel) -> Handler:
    """Build an assign_asset_persistent_id handler closed over the shared deps.

    Reads the BC-tier `DoiMinter` from `deps.equipment.doi_minter`
    (wired in `wire_equipment(deps)` per Lock 10). Calls
    `minter.mint(scheme, suffix)` to resolve the `PersistentIdentifier`,
    then runs the pure decider through the existing
    `make_asset_update_handler` factory. Returns the assigned
    `PersistentIdentifier` so the route can echo it in the 201 body.
    """
    # `deps.equipment` is attached as a `SimpleNamespace` by
    # `wire_equipment(deps)` before this handler binds (see Lock 10 in
    # [[project-asset-persistent-id-write-design]]). Pyright can't see the
    # dynamically-set attribute on the frozen Kernel; cast through Any.
    minter = cast("DoiMinter", deps.equipment.doi_minter)  # type: ignore[attr-defined]

    async def handler(
        command: AssignAssetPersistentId,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> PersistentIdentifier:
        persistent_id = await minter.mint(scheme=command.scheme, suffix=command.suffix)

        def decide_with_resolved(
            *,
            state: Asset | None,
            command: AssignAssetPersistentId,
            now: datetime,
        ) -> Sequence[AssetEvent]:
            return decide(state, command, persistent_id=persistent_id, now=now)

        inner = make_asset_update_handler(
            deps,
            command_name="AssignAssetPersistentId",
            log_prefix="assign_asset_persistent_id",
            decide_fn=decide_with_resolved,
        )
        await inner(
            command,
            principal_id=principal_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            surface_id=surface_id,
        )
        return persistent_id

    return handler

"""Application handler for the `decommission_asset` slice.

Longhand handler (cannot use `make_asset_update_handler` because it
loads a cross-aggregate projection BEFORE calling the decider). Loads
the Asset's current Mount-installation back-lookup from the
`proj_equipment_asset_location` projection, packages it into context,
and calls the pure decider with state + context.

Single-stream-write + projection-precondition pattern (mirrors
`install_asset` on the inverse side, and `decommission_mount`). The
same eventual-consistency caveat applies: the projection read and the
Asset stream append are not in one serializable txn; an `install_asset`
between read and append could leave the Asset Decommissioned with a
live Mount back-reference. Acceptable for v1 (rare operation, small
window, observable inconsistency via the conformance projection when
it ships); promote to SERIALIZABLE or PG advisory lock at first
incident.

The `AssetHasFixtureBinding` precondition is a STATE-based check on
`Asset.fixture_id`; the decider raises directly from state without
needing a projection lookup.

Not idempotency-wrapped: update-style commands are inherently
domain-idempotent at the aggregate level (second decommission hits
`AssetCannotDecommissionError` or one of the new HAS/IS guards); apply
only when cached-success-on-retry semantics are needed.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.decommission_asset.command import DecommissionAsset
from cora.equipment.features.decommission_asset.context import DecommissionAssetContext
from cora.equipment.features.decommission_asset.decider import decide
from cora.equipment.projections.asset_location import load_asset_location
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "DecommissionAsset"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every decommission_asset handler implements."""

    async def __call__(
        self,
        command: DecommissionAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build a decommission_asset handler closed over the shared deps."""

    async def handler(
        command: DecommissionAsset,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "decommission_asset.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "decommission_asset.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history = [from_stored(s) for s in stored]
        state = fold(history)

        # Projection precondition: which Mount currently holds this
        # Asset? Loaded BEFORE the decider so the pure decider raises
        # AssetIsInstalledError without I/O.
        # Pool-None short-circuit preserves the pre-tightening permissive
        # default (no location row) for the pool-less test path; in
        # production deps.pool is always set. Matches install_asset's
        # pool=None shape.
        currently_at = (
            await load_asset_location(deps.pool, command.asset_id)
            if deps.pool is not None
            else None
        )
        context = DecommissionAssetContext(currently_installed_at_mount_id=currently_at)

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
            decommissioned_by=ActorId(principal_id),
        )

        new_events = [
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=event.occurred_at,
                event_id=deps.id_generator.new_id(),
                command_name=_COMMAND_NAME,
                correlation_id=correlation_id,
                causation_id=causation_id,
                principal_id=principal_id,
            )
            for event in domain_events
        ]
        await deps.event_store.append(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "decommission_asset.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler

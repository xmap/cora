"""Application handler for the `add_plan_wire` slice.

Update-style handler that loads the Plan stream PLUS the Asset
streams the proposed wire references PLUS (when the target Asset is a
PseudoAxis Family member) every SOURCE Asset of existing wires that
already target the same Asset. Stays longhand for the same reason
`update_plan_default_parameters` does (6g-b): it loads more than one
stream, so it can't share a single-stream factory.

NOT idempotency-wrapped: wire-mutation is strict-not-idempotent at
the decider (re-add raises `PlanWireAlreadyExistsError`); apply
only when cached-success-on-retry semantics are needed.

## Handler shape

  1. Authorize the principal for the `AddPlanWire` command.
  2. Load the Plan stream and fold to current state.
  3. Load the two Asset streams referenced by the proposed wire
     (deduped to one load when source_asset_id == target_asset_id).
     Any reference that resolves to a non-existent Asset stream
     raises `AssetNotFoundError` (Equipment-BC error, 404), matching
     `define_plan` and `start_procedure`. The decider's
     `PlanWireAssetNotBoundError` is retained as defense-in-depth
     for the case where an Asset exists but isn't in `Plan.asset_ids`.
  4. Resolve PseudoAxis Family membership for the target Asset by
     loading each Family in `target_asset.family_ids` and matching
     on `name == "PseudoAxis"` (mirrors the
     `update_asset_partition_rule` slice handler). The set of
     PseudoAxis family ids is supplied to the decider via
     `pseudoaxis_family_ids` so the decider stays pure and tests can
     bypass the by-name lookup. When the target Asset matches, the
     handler also pre-loads every SOURCE Asset referenced by existing
     wires that already target the same Asset, so the fan-out
     validator can resolve source-port signal_types without I/O.
  5. Pass state + context + pseudoaxis_family_ids into the pure decider.
  6. Persist the resulting events.

Mirrors the loading shape of `update_plan_default_parameters` (one
upstream-stream load alongside the target-aggregate load) but uses
the `PlanWireContext` (slice-local) to thread Asset state into the
decider in a typed way.
"""

import asyncio
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import AssetNotFoundError
from cora.equipment.aggregates.asset.read import load_asset
from cora.equipment.aggregates.family.read import load_family
from cora.equipment.aggregates.family.state import FamilyName
from cora.infrastructure.event_envelope import to_new_event

if TYPE_CHECKING:
    from cora.equipment.aggregates.asset import Asset
    from cora.equipment.aggregates.family.state import Family
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.recipe.aggregates.plan import (
    PlanEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.recipe.errors import UnauthorizedError
from cora.recipe.features.add_plan_wire.command import AddPlanWire
from cora.recipe.features.add_plan_wire.context import PlanWireContext
from cora.recipe.features.add_plan_wire.decider import decide

_PSEUDOAXIS_FAMILY_NAME = FamilyName("PseudoAxis")

_STREAM_TYPE = "Plan"
_COMMAND_NAME = "AddPlanWire"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every add_plan_wire handler implements."""

    async def __call__(
        self,
        command: AddPlanWire,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an add_plan_wire handler closed over the shared deps."""

    async def handler(
        command: AddPlanWire,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "add_plan_wire.start",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            source_asset_id=str(command.source_asset_id),
            target_asset_id=str(command.target_asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_COMMAND_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "add_plan_wire.denied",
                command_name=_COMMAND_NAME,
                plan_id=str(command.plan_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.plan_id,
        )
        history: list[PlanEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Load the Assets referenced by the proposed wire (dedup the
        # self-loop case). Missing Asset streams raise
        # AssetNotFoundError (Equipment-BC error, 404), matching
        # define_plan and start_procedure. The decider's
        # PlanWireAssetNotBoundError stays in place as defense-in-
        # depth for Assets that exist but aren't bound to the Plan.
        asset_ids_to_load: set[UUID] = {
            command.source_asset_id,
            command.target_asset_id,
        }
        # When the target Asset already has incoming wires (other
        # sources fanning into the same target), pre-load each of
        # those source Assets too. The PseudoAxis fan-out validator
        # resolves source-side signal_types via assets_by_id and must
        # not perform I/O. Load these eagerly even before we know
        # whether the target is a PseudoAxis member: the cost is
        # bounded by the existing fan-in into the target Asset (zero
        # for non-PseudoAxis targets in practice) and avoids a second
        # round-trip after the family resolution.
        if state is not None:
            for existing in state.wires:
                if existing.target_asset_id == command.target_asset_id:
                    asset_ids_to_load.add(existing.source_asset_id)

        assets_by_id: dict[UUID, Asset] = {}
        for asset_id in sorted(asset_ids_to_load, key=str):
            asset = await load_asset(deps.event_store, asset_id)
            if asset is None:
                raise AssetNotFoundError(asset_id)
            assets_by_id[asset_id] = asset

        # Resolve PseudoAxis Family membership for the target Asset by
        # loading each Family in its family_ids and matching by name.
        # Mirrors update_asset_partition_rule handler. The decider
        # takes the resolved id set; tests bypass the load by passing
        # pseudoaxis_family_ids directly.
        target_asset = assets_by_id.get(command.target_asset_id)
        pseudoaxis_family_ids: frozenset[UUID] = frozenset()
        if target_asset is not None and target_asset.family_ids:
            family_ids = list(target_asset.family_ids)
            loaded: list[Family | None] = await asyncio.gather(
                *[load_family(deps.event_store, fid) for fid in family_ids],
            )
            pseudoaxis_family_ids = frozenset(
                f.id for f in loaded if f is not None and f.name == _PSEUDOAXIS_FAMILY_NAME
            )

        context = PlanWireContext(assets=assets_by_id)

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
            pseudoaxis_family_ids=pseudoaxis_family_ids,
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
            stream_id=command.plan_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "add_plan_wire.success",
            command_name=_COMMAND_NAME,
            plan_id=str(command.plan_id),
            source_asset_id=str(command.source_asset_id),
            target_asset_id=str(command.target_asset_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler

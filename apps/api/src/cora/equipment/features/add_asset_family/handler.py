"""Application handler for the `add_asset_family` slice.

Update-style handler shape — load + fold + decide + append. Not
idempotency-wrapped (domain-idempotent via
`AssetCannotAddFamilyError` on retry; same precedent as Subject
transitions / Asset lifecycle transitions).

**Stays longhand** (does not use `make_asset_update_handler`): the
command carries `family_id` in addition to `asset_id`, and the
handler logs `family_id` at start + success for diagnostic
visibility ("which family was added to which asset?"). Same
justification as `relocate_asset`. The factory is reserved for the
single-asset_id transition slices.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.asset import (
    AssetEvent,
    AssetModelMismatchError,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.aggregates.model import ModelNotFoundError, load_model
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.add_asset_family.command import AddAssetFamily
from cora.equipment.features.add_asset_family.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Asset"
_COMMAND_NAME = "AddAssetFamily"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every add_asset_family handler implements."""

    async def __call__(
        self,
        command: AddAssetFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an add_asset_family handler closed over the shared deps."""

    async def handler(
        command: AddAssetFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "add_asset_family.start",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            family_id=str(command.family_id),
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
                "add_asset_family.denied",
                command_name=_COMMAND_NAME,
                asset_id=str(command.asset_id),
                family_id=str(command.family_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.asset_id,
        )
        history: list[AssetEvent] = [from_stored(s) for s in stored]
        state = fold(history)

        # Cross-BC subset gate: when the Asset is bound to a Model
        # via model_id, the post-add family set must be a superset
        # of the Model's declared families. Lives in the handler
        # (not the decider) because the Model snapshot is loaded
        # at decide time from a stream the Asset aggregate does not
        # own. Same precedent as `update_asset_settings` loading
        # Family streams to validate against schemas. Single-stream
        # write discipline preserved: load Model read-only, append
        # only to the Asset stream.
        if state is not None and state.model_id is not None:
            model = await load_model(deps.event_store, state.model_id)
            if model is None:
                raise ModelNotFoundError(state.model_id)
            post_add_family_ids = state.family_ids | {command.family_id}
            if not model.declared_families.issubset(post_add_family_ids):
                raise AssetModelMismatchError(
                    asset_id=state.id,
                    model_id=state.model_id,
                    declared_families=model.declared_families,
                    asset_family_ids=post_add_family_ids,
                )

        domain_events = decide(state=state, command=command, now=now)

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
            "add_asset_family.success",
            command_name=_COMMAND_NAME,
            asset_id=str(command.asset_id),
            family_id=str(command.family_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler

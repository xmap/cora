"""Application handler for the `add_model_family` slice.

Update-style handler shape: load + fold + decide + append. Mirrors
the `add_asset_family` and `version_model` precedents for the
stream load + fold + decide + append spine, and the `define_model`
precedent for the cross-BC `list_all_family_ids` lookup that resolves
`command.family_id` against the Family registry before the decider
runs.

Not idempotency-wrapped: domain-idempotent via
`ModelFamilyAlreadyPresentError` on retry (mirrors
`add_asset_family`).

Cross-BC concern: the referenced `family_id` must resolve to a
registered Family stream (including Deprecated). On miss the
handler raises `FamilyNotFoundError(command.family_id)` (404) before
the decider sees the command, matching the `define_model`
operational pattern of surfacing missing-Family errors at the
application boundary. Family.deprecation is an authoring signal NOT
a runtime gate per the Model aggregate's design memo; adding a
Deprecated Family to a Model's declared set is permitted.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.family import FamilyNotFoundError, list_all_family_ids
from cora.equipment.aggregates.model import (
    ModelEvent,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.add_model_family.command import AddModelFamily
from cora.equipment.features.add_model_family.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Model"
_COMMAND_NAME = "AddModelFamily"

_log = get_logger(__name__)


class Handler(Protocol):
    """Callable interface every add_model_family handler implements."""

    async def __call__(
        self,
        command: AddModelFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def bind(deps: Kernel) -> Handler:
    """Build an add_model_family handler closed over the shared deps."""

    async def handler(
        command: AddModelFamily,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "add_model_family.start",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
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
                "add_model_family.denied",
                command_name=_COMMAND_NAME,
                model_id=str(command.model_id),
                family_id=str(command.family_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Cross-BC family lookup: the referenced Family must resolve.
        # Bulk single-query approach (cheap at pilot scale, <50 Families).
        # Trigger to switch to per-id load: facility Family count crosses
        # ~500 OR p95 of add_model_family crosses 200ms.
        known_family_ids = set(await list_all_family_ids(deps.pool))
        if command.family_id not in known_family_ids:
            _log.info(
                "add_model_family.family_not_found",
                command_name=_COMMAND_NAME,
                model_id=str(command.model_id),
                family_id=str(command.family_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
            )
            raise FamilyNotFoundError(command.family_id)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(
            stream_type=_STREAM_TYPE,
            stream_id=command.model_id,
        )
        history: list[ModelEvent] = [from_stored(s) for s in stored]
        state = fold(history)

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
            stream_id=command.model_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "add_model_family.success",
            command_name=_COMMAND_NAME,
            model_id=str(command.model_id),
            family_id=str(command.family_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
            new_version=current_version + len(new_events),
        )

    return handler

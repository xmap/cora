"""Application handler for the `define_model` slice.

Same shape as the locked cross-BC create-style command pattern
(register_actor / register_subject / define_zone / define_conduit
/ define_policy / define_family). Module-as-namespace: callers use
`from cora.equipment.features import define_model` then
`define_model.bind(deps)` returning a `define_model.Handler`.

Cross-BC concern: this handler loads `list_all_family_ids` from the
Family read repo before invoking the decider, and verifies every
element of `command.declared_family_ids` resolves to a registered
Family (including Deprecated). On miss, raises `FamilyNotFoundError`
(404) carrying the FIRST missing Family id. Operators iterating
through a multi-family catalog entry get a single missing id at
a time, matching the operational pattern.

Family.deprecation is an authoring signal NOT a runtime gate per
the Model aggregate's design memo; binding a Model to a Deprecated
Family is permitted, mirroring the Asset-to-Deprecated-Family
posture. The discovery-side filter (`list_family_ids`) is the wrong
helper here.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.family import FamilyNotFoundError, list_all_family_ids
from cora.equipment.aggregates.model import (
    PartNumber,
    event_type_name,
    model_stream_id,
    to_payload,
)
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.define_model.command import DefineModel
from cora.equipment.features.define_model.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Model"
_COMMAND_NAME = "DefineModel"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_model handler, the type returned by `bind()`.

    Has no idempotency_key kwarg. The cross-BC `with_idempotency`
    decorator wraps a bare Handler into an `IdempotentHandler`;
    production wiring in `wire.py` always wraps. Tests can use bare
    Handler directly when they don't need idempotency semantics.

    `causation_id` is the id of the event/message that triggered
    this command (None for HTTP / MCP root calls; sagas / process
    managers pass the upstream event's id).
    """

    async def __call__(
        self,
        command: DefineModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_model handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def bind(deps: Kernel) -> Handler:
    """Build a define_model handler closed over the shared deps."""

    async def handler(
        command: DefineModel,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_model.start",
            command_name=_COMMAND_NAME,
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
                "define_model.denied",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                causation_id=str(causation_id) if causation_id is not None else None,
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        # Cross-BC family_lookup: every declared family must resolve.
        # Bulk single-query approach (cheap at pilot scale, <50 Families).
        # Trigger to switch to per-id load: facility Family count crosses
        # ~500 OR p95 of define_model crosses 200ms.
        known_family_ids = set(await list_all_family_ids(deps.pool))
        missing = command.declared_family_ids - known_family_ids
        if missing:
            # Sorted for deterministic error ordering across runs; surface
            # the first missing id (operators get one at a time).
            first_missing = sorted(missing, key=str)[0]
            _log.info(
                "define_model.family_not_found",
                command_name=_COMMAND_NAME,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                first_missing_family_id=str(first_missing),
                missing_count=len(missing),
            )
            raise FamilyNotFoundError(first_missing)

        # The Model stream id is derived from the vendor key so the same
        # product converges across facilities. The random id is the
        # fallback for the unknown-pending-confirmation placeholder, and
        # is popped on every path so the per-event id keeps a stable slot.
        random_id = deps.id_generator.new_id()
        new_id = model_stream_id(
            command.manufacturer,
            PartNumber(command.part_number),
            new_id=random_id,
        )
        now = deps.clock.now()

        domain_events = decide(
            state=None,
            command=command,
            now=now,
            new_id=new_id,
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
            stream_id=new_id,
            expected_version=0,
            events=new_events,
        )

        _log.info(
            "define_model.success",
            command_name=_COMMAND_NAME,
            model_id=str(new_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            causation_id=str(causation_id) if causation_id is not None else None,
            event_count=len(new_events),
        )
        return new_id

    return handler

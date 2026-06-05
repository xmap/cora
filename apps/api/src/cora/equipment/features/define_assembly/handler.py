"""Application handler for the `define_assembly` slice.

Longhand create-style handler (cannot use a factory because it
loads N cross-aggregate references BEFORE calling the decider):

  1. Authz check (Deny -> UnauthorizedError).
  2. Load Family aggregate for `presents_as_family_id` + every
     FamilyId across the slot set's required_family_ids; collect the
     missing ones into context.
  3. Call pure decider with state=None + context + command +
     now + new_id.
  4. Wrap emitted events and append to the Assembly stream
     (single-stream write with expected_version=0 for genesis).

Pattern mirrors register_mount's longhand-with-precondition shape
but checks N references instead of one. The per-id lookup strategy
and its concurrency are owned by `find_missing_families_per_id`
in family/read.py.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.assembly import event_type_name, to_payload
from cora.equipment.aggregates.family import find_missing_families_per_id
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.define_assembly.command import DefineAssembly
from cora.equipment.features.define_assembly.context import DefineAssemblyContext
from cora.equipment.features.define_assembly.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Assembly"
_COMMAND_NAME = "DefineAssembly"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare define_assembly handler - what `bind()` returns."""

    async def __call__(
        self,
        command: DefineAssembly,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID: ...


class IdempotentHandler(Protocol):
    """define_assembly handler with Idempotency-Key support."""

    async def __call__(
        self,
        command: DefineAssembly,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
        idempotency_key: str | None = None,
    ) -> UUID: ...


def _referenced_family_ids(command: DefineAssembly) -> frozenset[UUID]:
    """Collect every FamilyId the Assembly references at define time.

    Union of `presents_as_family_id` and every slot's required_family_ids.
    Returned as a frozenset so handler loads are de-duplicated when
    multiple slots share a Family.
    """
    ids: set[UUID] = {command.presents_as_family_id}
    for slot in command.required_slots:
        ids.update(slot.required_family_ids)
    return frozenset(ids)


def bind(deps: Kernel) -> Handler:
    """Build a define_assembly handler closed over the shared deps."""

    async def handler(
        command: DefineAssembly,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> UUID:
        _log.info(
            "define_assembly.start",
            command_name=_COMMAND_NAME,
            name=command.name,
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
                "define_assembly.denied",
                command_name=_COMMAND_NAME,
                name=command.name,
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        new_id = deps.id_generator.new_id()
        now = deps.clock.now()

        family_ids = _referenced_family_ids(command)
        missing = await find_missing_families_per_id(deps.event_store, family_ids)
        context = DefineAssemblyContext(missing_family_ids=missing)

        domain_events = decide(
            state=None,
            command=command,
            context=context,
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
            "define_assembly.success",
            command_name=_COMMAND_NAME,
            assembly_id=str(new_id),
            name=command.name,
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
        )
        return new_id

    return handler

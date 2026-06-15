"""Application handler for the `version_assembly` slice.

Longhand update-style handler (cannot use a factory because it
loads N cross-aggregate Family streams BEFORE calling the decider,
same shape as define_assembly):

  1. Authz check (Deny -> UnauthorizedError).
  2. Load the Assembly stream once via `event_store.load`, fold to
     state, and reuse the same call's `current_version` for the
     optimistic-concurrency append (matches decommission_mount's
     single-load shape).
  3. Edge-load each Role in `presents_as` via RoleLookup, and load the
     Family aggregate for every FamilyId across the slot set's
     required_family_ids (de-duplicated via frozenset). Build context
     with missing_role_ids + missing_family_ids.
  4. Call pure decider with state + context + command + now.
  5. Wrap emitted events and append to the Assembly stream at the
     captured version.
"""

from typing import Protocol
from uuid import UUID

from cora.equipment.aggregates.assembly import (
    event_type_name,
    fold,
    from_stored,
    resolve_sub_assembly_pins,
    to_payload,
)
from cora.equipment.aggregates.family import find_missing_families_per_id
from cora.equipment.errors import UnauthorizedError
from cora.equipment.features.version_assembly.command import VersionAssembly
from cora.equipment.features.version_assembly.context import VersionAssemblyContext
from cora.equipment.features.version_assembly.decider import decide
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID

_STREAM_TYPE = "Assembly"
_COMMAND_NAME = "VersionAssembly"

_log = get_logger(__name__)


class Handler(Protocol):
    """Bare version_assembly handler - what `bind()` returns."""

    async def __call__(
        self,
        command: VersionAssembly,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None: ...


def _referenced_family_ids(command: VersionAssembly) -> frozenset[UUID]:
    """Collect every FamilyId the new version references.

    Every slot's required_family_ids. Returned as a frozenset so
    handler loads are de-duplicated when multiple slots share a Family.
    """
    ids: set[UUID] = set()
    for slot in command.required_slots:
        ids.update(slot.required_family_ids)
    return frozenset(ids)


def bind(deps: Kernel) -> Handler:
    """Build a version_assembly handler closed over the shared deps."""

    async def handler(
        command: VersionAssembly,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        _log.info(
            "version_assembly.start",
            command_name=_COMMAND_NAME,
            assembly_id=str(command.assembly_id),
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
                "version_assembly.denied",
                command_name=_COMMAND_NAME,
                assembly_id=str(command.assembly_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        now = deps.clock.now()

        stored, current_version = await deps.event_store.load(_STREAM_TYPE, command.assembly_id)
        state = fold([from_stored(s) for s in stored])

        family_ids = _referenced_family_ids(command)
        missing = await find_missing_families_per_id(deps.event_store, family_ids)
        missing_roles: set[UUID] = set()
        for role_id in command.presents_as:
            if await deps.role_lookup.lookup(role_id) is None:
                missing_roles.add(role_id)
        sub_resolution = await resolve_sub_assembly_pins(
            deps.event_store,
            command.required_sub_assemblies,
            parent_slot_names=frozenset(slot.slot_name.value for slot in command.required_slots),
        )
        context = VersionAssemblyContext(
            missing_family_ids=missing,
            missing_role_ids=frozenset(missing_roles),
            sub_assembly_missing_ids=sub_resolution.missing_ids,
            sub_assembly_hash_mismatches=sub_resolution.hash_mismatches,
            sub_assembly_too_deep_ids=sub_resolution.too_deep_ids,
            sub_assembly_leaf_collisions=sub_resolution.leaf_slot_collisions,
        )

        domain_events = decide(
            state=state,
            command=command,
            context=context,
            now=now,
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
            stream_id=command.assembly_id,
            expected_version=current_version,
            events=new_events,
        )

        _log.info(
            "version_assembly.success",
            command_name=_COMMAND_NAME,
            assembly_id=str(command.assembly_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            event_count=len(new_events),
        )

    return handler

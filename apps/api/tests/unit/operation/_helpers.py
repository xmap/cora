"""Shared event-seeding helpers for Operation BC unit tests.

Hoisted at rule-of-three: complete_procedure / abort_procedure /
append_activities handler tests all carried byte-identical
`_seed_running_procedure` bodies (Registered + Started events
appended directly to an in-memory event store). Gate-review
trigger fired the hoist (consolidating before truncate_procedure
adds a fourth instance).

Per-test files import what they need; this module owns no test
constants (procedure_id, principal_id, etc.) — those stay local
to each test file so each test still controls its own ID space
and FixedIdGenerator queue.
"""

from datetime import datetime
from uuid import UUID, uuid4

from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.operation.aggregates.procedure import (
    ProcedureCompleted,
    ProcedureIterationStarted,
    ProcedureRegistered,
    ProcedureStarted,
    event_type_name,
    to_payload,
)


async def seed_registered_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    name: str = "Vessel-A bakeout",
    kind: str = "bakeout",
    target_asset_ids: tuple[UUID, ...] | None = None,
    parent_run_id: UUID | None = None,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append ProcedureRegistered to land the Procedure in `Defined`."""
    event = ProcedureRegistered(
        procedure_id=procedure_id,
        name=name,
        kind=kind,
        target_asset_ids=target_asset_ids or (),
        parent_run_id=parent_run_id,
        occurred_at=when,
    )
    new_event = to_new_event(
        event_type=event_type_name(event),
        payload=to_payload(event),
        occurred_at=event.occurred_at,
        event_id=uuid4(),
        command_name="RegisterProcedure",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=0,
        events=[new_event],
    )


async def seed_running_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append Registered + Started to land the Procedure in `Running`."""
    await seed_registered_procedure(
        store,
        procedure_id=procedure_id,
        when=when,
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    started = ProcedureStarted(procedure_id=procedure_id, occurred_at=when)
    new_event = to_new_event(
        event_type=event_type_name(started),
        payload=to_payload(started),
        occurred_at=started.occurred_at,
        event_id=uuid4(),
        command_name="StartProcedure",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=1,
        events=[new_event],
    )


async def seed_completed_procedure(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append Registered + Started + Completed to reach a terminal `Completed`."""
    await seed_running_procedure(
        store,
        procedure_id=procedure_id,
        when=when,
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    completed = ProcedureCompleted(procedure_id=procedure_id, occurred_at=when)
    new_event = to_new_event(
        event_type=event_type_name(completed),
        payload=to_payload(completed),
        occurred_at=completed.occurred_at,
        event_id=uuid4(),
        command_name="CompleteProcedure",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=2,
        events=[new_event],
    )


async def seed_running_procedure_with_open_iteration(
    store: InMemoryEventStore,
    *,
    procedure_id: UUID,
    iteration_index: int = 1,
    when: datetime,
    correlation_id: UUID,
    principal_id: UUID,
) -> None:
    """Append Registered + Started + IterationStarted to leave one iteration open."""
    await seed_running_procedure(
        store,
        procedure_id=procedure_id,
        when=when,
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    started = ProcedureIterationStarted(
        procedure_id=procedure_id,
        iteration_index=iteration_index,
        occurred_at=when,
    )
    new_event = to_new_event(
        event_type=event_type_name(started),
        payload=to_payload(started),
        occurred_at=started.occurred_at,
        event_id=uuid4(),
        command_name="StartProcedureIteration",
        correlation_id=correlation_id,
        principal_id=principal_id,
    )
    await store.append(
        stream_type="Procedure",
        stream_id=procedure_id,
        expected_version=2,
        events=[new_event],
    )


__all__ = [
    "seed_completed_procedure",
    "seed_registered_procedure",
    "seed_running_procedure",
    "seed_running_procedure_with_open_iteration",
]

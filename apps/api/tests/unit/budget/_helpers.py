"""Shared builders for budget unit tests.

One `make_allocation` state factory plus one event-stream seeder (the
campaign `_helpers.py` precedent) so the five slice test trios do not
each re-declare the aggregate's full constructor as it grows fields.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from cora.budget.aggregates.allocation import (
    Allocation,
    AllocationActivated,
    AllocationEvent,
    AllocationGranted,
    AllocationNote,
    AllocationStatus,
    event_type_name,
    to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId

GRANTED_AT = datetime(2026, 7, 12, 9, 0, 0, tzinfo=UTC)
ACTIVATED_AT = datetime(2026, 7, 12, 10, 0, 0, tzinfo=UTC)

GRANTED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000011"))
ACTIVATED_BY = ActorId(UUID("01900000-0000-7000-8000-000000000022"))


def make_allocation(
    status: AllocationStatus,
    *,
    allocation_id: UUID | None = None,
    ceiling_usd: float = 25000.0,
    campaign_id: UUID | None = None,
) -> Allocation:
    """Build an Allocation in the given status with plausible window fields.

    Statuses past Granted carry `activated_at` / `activated_by` so
    deciders and handlers that read the window (seal) see the shape a
    real fold produces.
    """
    activated = status is not AllocationStatus.GRANTED
    return Allocation(
        id=allocation_id or uuid4(),
        ceiling_usd=ceiling_usd,
        note=AllocationNote("FY26 imaging award"),
        campaign_id=campaign_id,
        granted_at=GRANTED_AT,
        granted_by=GRANTED_BY,
        status=status,
        activated_at=ACTIVATED_AT if activated else None,
        activated_by=ACTIVATED_BY if activated else None,
    )


def granted_event(
    allocation_id: UUID,
    *,
    ceiling_usd: float = 25000.0,
    campaign_id: UUID | None = None,
) -> AllocationGranted:
    return AllocationGranted(
        allocation_id=allocation_id,
        ceiling_usd=ceiling_usd,
        campaign_id=campaign_id,
        note="FY26 imaging award",
        granted_by=GRANTED_BY,
        occurred_at=GRANTED_AT,
    )


def activated_event(allocation_id: UUID) -> AllocationActivated:
    return AllocationActivated(
        allocation_id=allocation_id,
        activated_by=ACTIVATED_BY,
        occurred_at=ACTIVATED_AT,
    )


async def seed_allocation_events(
    store: InMemoryEventStore,
    allocation_id: UUID,
    *events: AllocationEvent,
) -> None:
    """Append the given domain events to the Allocation stream in order.

    Wraps each through the real codecs (`event_type_name` /
    `to_payload`) so handler tests replay exactly what production
    appends would have stored.
    """
    for version, event in enumerate(events):
        await store.append(
            stream_type="Allocation",
            stream_id=allocation_id,
            expected_version=version,
            events=[
                to_new_event(
                    event_type=event_type_name(event),
                    payload=to_payload(event),
                    occurred_at=event.occurred_at,
                    event_id=uuid4(),
                    command_name="Seed",
                    correlation_id=uuid4(),
                    causation_id=None,
                    principal_id=GRANTED_BY,
                )
            ],
        )

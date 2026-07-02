"""End-to-end: RunActorInvolvementProjection + the lookup adapter against
real Postgres.

The projection folds TWO streams (Run + Decision), so this test appends
raw events directly to the event store (the projection's real input),
drains, and reads back through `PostgresRunActorInvolvementLookup`. The
full start_run -> supervise -> hold chain via handlers is the E4 scenario
in Slice 3; here we isolate the cross-stream fold + the partial-index
in-flight query against the real schema (the CHECK constraints and the
partial index only exist in Postgres, not the mocked unit tests).

Pins:
  - RunStarted -> a 'starter' row keyed on the envelope principal_id.
  - RunSupervision DecisionRegistered -> a 'supervisor' row keyed on
    decided_by, for the run in the decision inputs.
  - Both actors' in-flight lookup returns the run while Running / Held.
  - A terminal Run event drops the run from BOTH actors' in-flight
    lookup (partial index excludes terminal status).
  - An actor behind no in-flight run gets the empty set.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.event_store import EventStore
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run._projections import register_run_projections
from cora.run.adapters import PostgresRunActorInvolvementLookup
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
# A terminal event's principal is irrelevant to the projection (only
# RunStarted's envelope principal keys a row); a stable throwaway keeps
# the append well-formed.
_SYSTEM_ID = UUID("01900000-0000-7000-8000-0000000000ff")


async def _append_run_started(
    store: EventStore, *, run_id: UUID, starter_id: UUID, event_id: UUID
) -> None:
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type="RunStarted",
                payload={
                    "run_id": str(run_id),
                    "name": "lights-out tomography",
                    "plan_id": str(uuid4()),
                    "subject_id": None,
                    "occurred_at": _NOW.isoformat(),
                },
                occurred_at=_NOW,
                event_id=event_id,
                command_name="StartRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=starter_id,
            )
        ],
    )


async def _append_run_terminal(
    store: EventStore,
    *,
    run_id: UUID,
    expected_version: int,
    event_id: UUID,
) -> None:
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=expected_version,
        events=[
            to_new_event(
                event_type="RunCompleted",
                payload={"run_id": str(run_id), "occurred_at": _NOW.isoformat()},
                occurred_at=_NOW,
                event_id=event_id,
                command_name="CompleteRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_SYSTEM_ID,
            )
        ],
    )


async def _append_supervision_decision(
    store: EventStore,
    *,
    decision_id: UUID,
    supervisor_id: UUID,
    run_id: UUID,
    event_id: UUID,
) -> None:
    await store.append(
        stream_type="Decision",
        stream_id=decision_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type="DecisionRegistered",
                payload={
                    "decision_id": str(decision_id),
                    "decided_by": str(supervisor_id),
                    "context": "RunSupervision",
                    "choice": "Hold",
                    "parent_id": None,
                    "override_kind": None,
                    "rule": "agent:RunSupervisor:v1",
                    "reasoning": None,
                    "confidence": None,
                    "confidence_source": None,
                    "alternatives": [],
                    "inputs": {"run_id": str(run_id)},
                    "reasoning_signature": None,
                    "occurred_at": _NOW.isoformat(),
                },
                occurred_at=_NOW,
                event_id=event_id,
                command_name="RegisterDecision",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=supervisor_id,
            )
        ],
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_run_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_starter_and_supervisor_both_inflight_then_dropped_on_terminal(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW)
    store = deps.event_store
    lookup = PostgresRunActorInvolvementLookup(db_pool)

    run_id = uuid4()
    starter_id = uuid4()  # the operator who started the run
    supervisor_id = uuid4()  # the agent supervising it

    await _append_run_started(store, run_id=run_id, starter_id=starter_id, event_id=uuid4())
    await _append_supervision_decision(
        store,
        decision_id=uuid4(),
        supervisor_id=supervisor_id,
        run_id=run_id,
        event_id=uuid4(),
    )
    await _drain(db_pool)

    # Both the starter and the supervisor are "behind" this in-flight run.
    assert await lookup.find_inflight_run_ids(starter_id) == frozenset({run_id})
    assert await lookup.find_inflight_run_ids(supervisor_id) == frozenset({run_id})

    # A terminal Run event drops it from BOTH actors' in-flight view.
    await _append_run_terminal(store, run_id=run_id, expected_version=1, event_id=uuid4())
    await _drain(db_pool)

    assert await lookup.find_inflight_run_ids(starter_id) == frozenset()
    assert await lookup.find_inflight_run_ids(supervisor_id) == frozenset()


@pytest.mark.integration
async def test_lookup_returns_empty_for_uninvolved_actor(
    db_pool: asyncpg.Pool,
) -> None:
    lookup = PostgresRunActorInvolvementLookup(db_pool)
    assert await lookup.find_inflight_run_ids(uuid4()) == frozenset()


@pytest.mark.integration
async def test_supervision_decision_without_starter_row_creates_no_phantom(
    db_pool: asyncpg.Pool,
) -> None:
    """A RunSupervision Decision for a run with no starter row (e.g. a
    principal-less RunStarted that was skipped) must NOT create a phantom
    supervisor row that would appear in-flight forever."""
    deps = build_postgres_deps(db_pool, now=_NOW)
    store = deps.event_store
    lookup = PostgresRunActorInvolvementLookup(db_pool)

    orphan_run_id = uuid4()
    supervisor_id = uuid4()

    await _append_supervision_decision(
        store,
        decision_id=uuid4(),
        supervisor_id=supervisor_id,
        run_id=orphan_run_id,
        event_id=uuid4(),
    )
    await _drain(db_pool)

    assert await lookup.find_inflight_run_ids(supervisor_id) == frozenset()


@pytest.mark.integration
async def test_held_run_still_counts_as_inflight(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW)
    store = deps.event_store
    lookup = PostgresRunActorInvolvementLookup(db_pool)

    run_id = uuid4()
    starter_id = uuid4()

    await _append_run_started(store, run_id=run_id, starter_id=starter_id, event_id=uuid4())
    # Hold the run: still in-flight (Held is a non-terminal status).
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type="RunHeld",
                payload={"run_id": str(run_id), "occurred_at": _NOW.isoformat()},
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="HoldRun",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=starter_id,
            )
        ],
    )
    await _drain(db_pool)

    assert await lookup.find_inflight_run_ids(starter_id) == frozenset({run_id})

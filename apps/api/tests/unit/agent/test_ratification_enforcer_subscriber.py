"""Unit tests for the RatificationEnforcer subscribers (consequence gate, Gate IV).

Against an in-memory kernel: the hold subscriber reacts to RatificationRequested
by holding the target Running run; the release subscriber reacts to
RatificationGranted by resuming the held run. Both guard status (Running for hold,
Held for release), stand down when unseeded, and are no-ops off the happy path.
"""

# white-box test of the subscriber internals
# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_ratification_enforcer import (
    RATIFICATION_ENFORCER_AGENT_ID,
    seed_ratification_enforcer_agent,
)
from cora.agent.subscribers.ratification_hold import make_ratification_hold_subscriber
from cora.agent.subscribers.ratification_release import make_ratification_release_subscriber
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.ports.event_store import EventStore, StoredEvent
from cora.run.aggregates.run import RunHeld, RunStarted, RunStatus, load_run
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from cora.trust.aggregates.ratification import event_type_name as rat_event_type_name
from cora.trust.aggregates.ratification import to_payload as rat_to_payload
from cora.trust.aggregates.ratification.events import RatificationRequested

_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)


def _kernel() -> Kernel:
    return make_inmemory_kernel(
        settings=Settings(),  # type: ignore[call-arg]
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


async def _seed_running_run(store: EventStore) -> UUID:
    run_id = uuid4()
    started = RunStarted(
        run_id=run_id, name="gated run", plan_id=uuid4(), subject_id=uuid4(), occurred_at=_NOW
    )
    await store.append(
        "Run",
        run_id,
        0,
        [
            to_new_event(
                event_type=run_event_type_name(started),
                payload=run_to_payload(started),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="StartRun",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
        ],
    )
    return run_id


async def _seed_held_run(store: EventStore, *, held_by: UUID | None = None) -> UUID:
    """Seed a Running run then a RunHeld. `held_by` is the hold's envelope principal
    (who placed the hold); defaults to the enforcer, so the release's correlation
    guard treats it as its own hold. Pass a foreign id to simulate a kill-switch /
    operator hold the release must NOT clear."""
    run_id = await _seed_running_run(store)
    held = RunHeld(run_id=run_id, decided_by_decision_id=None, occurred_at=_NOW)
    await store.append(
        "Run",
        run_id,
        1,
        [
            to_new_event(
                event_type=run_event_type_name(held),
                payload=run_to_payload(held),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="HoldRun",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=held_by if held_by is not None else RATIFICATION_ENFORCER_AGENT_ID,
            )
        ],
    )
    return run_id


async def _seed_ratification(store: EventStore, *, target_run_id: UUID) -> UUID:
    """Append a RatificationRequested so load_ratification resolves the target."""
    ratification_id = uuid4()
    requested = RatificationRequested(
        ratification_id=ratification_id,
        target_action_id=target_run_id,
        command_name="StopRun",
        consequence_class="irreversible",
        requested_by=uuid4(),
        occurred_at=_NOW,
    )
    await store.append(
        "Ratification",
        ratification_id,
        0,
        [
            to_new_event(
                event_type=rat_event_type_name(requested),
                payload=rat_to_payload(requested),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="RequestRatification",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
        ],
    )
    return ratification_id


def _requested_event(*, target_run_id: UUID) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Ratification",
        stream_id=uuid4(),
        version=1,
        event_type="RatificationRequested",
        schema_version=1,
        payload={
            "ratification_id": str(uuid4()),
            "target_action_id": str(target_run_id),
            "command_name": "StopRun",
            "consequence_class": "irreversible",
            "requested_by": str(uuid4()),
            "occurred_at": _NOW.isoformat(),
        },
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


def _granted_event(*, ratification_id: UUID) -> StoredEvent:
    return StoredEvent(
        position=2,
        event_id=uuid4(),
        stream_type="Ratification",
        stream_id=ratification_id,
        version=2,
        event_type="RatificationGranted",
        schema_version=1,
        payload={"ratification_id": str(ratification_id), "occurred_at": _NOW.isoformat()},
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


def _denied_event(*, ratification_id: UUID) -> StoredEvent:
    return StoredEvent(
        position=2,
        event_id=uuid4(),
        stream_type="Ratification",
        stream_id=ratification_id,
        version=2,
        event_type="RatificationDenied",
        schema_version=1,
        payload={
            "ratification_id": str(ratification_id),
            "reason": "co-sign refused",
            "occurred_at": _NOW.isoformat(),
        },
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


# --- hold subscriber ---


@pytest.mark.unit
async def test_hold_subscriber_holds_the_target_running_run() -> None:
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    run_id = await _seed_running_run(kernel.event_store)
    sub = make_ratification_hold_subscriber(kernel)

    await sub.apply(_requested_event(target_run_id=run_id), conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None and state.status is RunStatus.HELD


@pytest.mark.unit
async def test_hold_subscriber_noop_when_run_not_running() -> None:
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    run_id = await _seed_held_run(kernel.event_store)  # already Held
    sub = make_ratification_hold_subscriber(kernel)

    await sub.apply(_requested_event(target_run_id=run_id), conn=None)  # type: ignore[arg-type]

    # Still exactly one RunHeld (no second hold appended).
    stored, _ = await kernel.event_store.load("Run", run_id)
    assert sum(1 for s in stored if s.event_type == "RunHeld") == 1


@pytest.mark.unit
async def test_hold_subscriber_stands_down_when_unseeded() -> None:
    kernel = _kernel()  # NOT seeded
    run_id = await _seed_running_run(kernel.event_store)
    sub = make_ratification_hold_subscriber(kernel)

    await sub.apply(_requested_event(target_run_id=run_id), conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None and state.status is RunStatus.RUNNING


# --- release subscriber ---


@pytest.mark.unit
async def test_release_subscriber_resumes_the_held_run() -> None:
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    run_id = await _seed_held_run(kernel.event_store)
    ratification_id = await _seed_ratification(kernel.event_store, target_run_id=run_id)
    sub = make_ratification_release_subscriber(kernel)

    await sub.apply(_granted_event(ratification_id=ratification_id), conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None and state.status is RunStatus.RUNNING


@pytest.mark.unit
async def test_release_subscriber_noop_when_run_not_held() -> None:
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    run_id = await _seed_running_run(kernel.event_store)  # Running, not Held
    ratification_id = await _seed_ratification(kernel.event_store, target_run_id=run_id)
    sub = make_ratification_release_subscriber(kernel)

    await sub.apply(_granted_event(ratification_id=ratification_id), conn=None)  # type: ignore[arg-type]

    stored, _ = await kernel.event_store.load("Run", run_id)
    assert sum(1 for s in stored if s.event_type == "RunResumed") == 0


@pytest.mark.unit
async def test_release_subscriber_ignores_unknown_ratification() -> None:
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    sub = make_ratification_release_subscriber(kernel)
    # A Granted event whose ratification stream does not exist -> no crash, no-op.
    await sub.apply(_granted_event(ratification_id=uuid4()), conn=None)  # type: ignore[arg-type]


@pytest.mark.unit
async def test_release_subscriber_resumes_on_denial() -> None:
    """A DENIED ratification also un-parks the run: leaving it Held forever would
    make the reversible hold un-reversible. The run returns to Running; the stop
    stays un-admitted because coverage is never Granted."""
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    run_id = await _seed_held_run(kernel.event_store)
    ratification_id = await _seed_ratification(kernel.event_store, target_run_id=run_id)
    sub = make_ratification_release_subscriber(kernel)

    await sub.apply(_denied_event(ratification_id=ratification_id), conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None and state.status is RunStatus.RUNNING


@pytest.mark.unit
async def test_release_does_not_clear_a_foreign_hold() -> None:
    """The load-bearing correlation guard: a run Held by a DIFFERENT concern (e.g.
    the kill-switch, a foreign principal) must NOT be resumed by a stray
    RatificationGranted, or the release would defeat that hold."""
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    foreign_holder = uuid4()  # e.g. the kill-switch's authority_revocation_holder
    run_id = await _seed_held_run(kernel.event_store, held_by=foreign_holder)
    ratification_id = await _seed_ratification(kernel.event_store, target_run_id=run_id)
    sub = make_ratification_release_subscriber(kernel)

    await sub.apply(_granted_event(ratification_id=ratification_id), conn=None)  # type: ignore[arg-type]

    # The foreign hold survives: still Held, no RunResumed appended.
    state = await load_run(kernel.event_store, run_id)
    assert state is not None and state.status is RunStatus.HELD
    stored, _ = await kernel.event_store.load("Run", run_id)
    assert sum(1 for s in stored if s.event_type == "RunResumed") == 0


@pytest.mark.unit
async def test_make_subscribers_wire_metadata() -> None:
    kernel = _kernel()
    hold = make_ratification_hold_subscriber(kernel)
    release = make_ratification_release_subscriber(kernel)
    assert hold.name == "ratification_hold"
    assert hold.subscribed_event_types == frozenset({"RatificationRequested"})
    assert release.name == "ratification_release"
    assert release.subscribed_event_types == frozenset(
        {"RatificationGranted", "RatificationDenied"}
    )

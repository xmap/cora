"""Unit tests for `attempt_debrief_lease` + `derive_lease_event_id`.

Per [[project-run-debriefer-lease-design]]. Pins:
- lease event_id determinism per `(run_id, agent_id, terminal_event_id)`
- success on empty Run stream (lease acquired)
- success on same-agent retry (idempotent on lease already present)
- conflict-loss on different-agent prior lease
- conflict-loss on concurrent append via mock ConcurrencyError
- conflict-loss with None winner when version moved by non-lease event
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4
from uuid import uuid5 as _uuid5

import pytest

from cora.agent._subscriber_lease import (
    attempt_debrief_lease,
    derive_lease_event_id,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.ports.event_store import NewEvent, StoredEvent, StreamAppend
from cora.run.aggregates.run.events import (
    RunStarted,
    event_type_name,
    to_payload,
)

_NOW = datetime(2026, 6, 4, 12, 0, 0, tzinfo=UTC)
_COMMAND_NAME = "TestSubscriber"


def _terminal_event(
    *,
    run_id: UUID,
    event_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> StoredEvent:
    """Build a StoredEvent stand-in for the terminal Run event the
    subscriber received from the projection worker."""
    return StoredEvent(
        position=10,
        event_id=event_id or uuid4(),
        stream_type="Run",
        stream_id=run_id,
        version=5,
        event_type="RunCompleted",
        schema_version=1,
        payload={"run_id": str(run_id), "occurred_at": _NOW.isoformat()},
        correlation_id=correlation_id or uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
    )


async def _seed_run(store: InMemoryEventStore, run_id: UUID) -> None:
    """Seed a minimal RunStarted event so the lease helper's
    `event_store.load("Run", run_id)` returns a non-empty stream."""
    started = RunStarted(
        run_id=run_id,
        name="R",
        plan_id=uuid4(),
        subject_id=None,
        raid=None,
        override_parameters={},
        effective_parameters={},
        trigger_source="operator",
        external_refs=(),
        acknowledged_cautions=(),
        campaign_id=None,
        decided_by_decision_id=None,
        pinned_calibration_ids=(),
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(started),
                payload=to_payload(started),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            ),
        ],
    )


@pytest.mark.unit
def test_derive_lease_event_id_is_deterministic_for_same_triple() -> None:
    run_id = uuid4()
    agent_id = uuid4()
    terminal_id = uuid4()
    a = derive_lease_event_id(
        run_id=run_id, debriefer_agent_id=agent_id, terminal_event_id=terminal_id
    )
    b = derive_lease_event_id(
        run_id=run_id, debriefer_agent_id=agent_id, terminal_event_id=terminal_id
    )
    assert a == b


@pytest.mark.unit
def test_derive_lease_event_id_differs_across_agents_for_same_terminal_event() -> None:
    """Cross-agent contention plays out on stream version, not event_id
    UNIQUE; different agents producing different event_ids is the
    load-bearing condition that makes the race work."""
    run_id = uuid4()
    terminal_id = uuid4()
    a = derive_lease_event_id(
        run_id=run_id, debriefer_agent_id=uuid4(), terminal_event_id=terminal_id
    )
    b = derive_lease_event_id(
        run_id=run_id, debriefer_agent_id=uuid4(), terminal_event_id=terminal_id
    )
    assert a != b


@pytest.mark.unit
def test_derive_lease_event_id_matches_explicit_uuid5_seed() -> None:
    """The seed format is contract: any operator reading the event log
    can recompute the lease event_id by hand using the documented
    `uuid5(run_id, f'lease:{terminal_event_id}:{agent_id}')` shape."""
    run_id = uuid4()
    agent_id = uuid4()
    terminal_id = uuid4()
    expected = _uuid5(run_id, f"lease:{terminal_id}:{agent_id}")
    actual = derive_lease_event_id(
        run_id=run_id, debriefer_agent_id=agent_id, terminal_event_id=terminal_id
    )
    assert actual == expected


@pytest.mark.unit
async def test_attempt_debrief_lease_on_clean_stream_acquires_lease() -> None:
    store = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(store, run_id)
    agent_id = uuid4()
    terminal = _terminal_event(run_id=run_id)

    success, winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert success is True
    assert winner is None
    stored, _v = await store.load("Run", run_id)
    lease_events = [e for e in stored if e.event_type == "DecisionDebriefRequested"]
    assert len(lease_events) == 1
    assert lease_events[0].payload["debriefer_agent_id"] == str(agent_id)
    assert lease_events[0].payload["terminal_event_id"] == str(terminal.event_id)


@pytest.mark.unit
async def test_attempt_debrief_lease_prior_same_agent_lease_returns_success_idempotently() -> None:
    """Same-agent retry: a re-fire after process crash sees its own
    prior lease on the stream + returns success without re-appending."""
    store = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(store, run_id)
    agent_id = uuid4()
    terminal = _terminal_event(run_id=run_id)

    # First call: acquires lease.
    await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    # Second call: idempotent.
    success, winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert success is True
    assert winner is None
    stored, _v = await store.load("Run", run_id)
    lease_events = [e for e in stored if e.event_type == "DecisionDebriefRequested"]
    assert len(lease_events) == 1  # no duplicate append


@pytest.mark.unit
async def test_attempt_debrief_lease_with_prior_different_agent_lease_returns_winner() -> None:
    store = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(store, run_id)
    winner_id = uuid4()
    loser_id = uuid4()
    terminal = _terminal_event(run_id=run_id)

    await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=winner_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    success, observed_winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=loser_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert success is False
    assert observed_winner == winner_id
    stored, _v = await store.load("Run", run_id)
    lease_events = [e for e in stored if e.event_type == "DecisionDebriefRequested"]
    assert len(lease_events) == 1  # loser did not append


@pytest.mark.unit
async def test_attempt_debrief_lease_independent_terminal_events_both_acquire() -> None:
    """Two distinct terminal events on the same Run (e.g., a Run that
    was terminated and re-debriefed against a later terminal marker)
    each get their own lease independently."""
    store = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(store, run_id)
    agent_id = uuid4()
    terminal_a = _terminal_event(run_id=run_id)
    terminal_b = _terminal_event(run_id=run_id)

    a_success, _ = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal_a,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )
    b_success, _ = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal_b,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert a_success is True
    assert b_success is True
    stored, _v = await store.load("Run", run_id)
    lease_events = [e for e in stored if e.event_type == "DecisionDebriefRequested"]
    assert len(lease_events) == 2


@pytest.mark.unit
async def test_attempt_debrief_lease_with_late_run_event_advancing_version_acquires() -> None:
    """The helper re-loads the Run stream to pick up its current
    version before appending. A late-arriving non-lease Run event
    (e.g., RunAddedToCampaign from Campaign BC) between subscriber
    `load_run` and lease attempt advances the version; the helper
    handles this by re-reading and using the fresh expected_version
    (memo Lock: 'expected_version MUST be re-fetched immediately
    before append')."""
    from cora.run.aggregates.run.events import RunAddedToCampaign

    store = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(store, run_id)

    added = RunAddedToCampaign(run_id=run_id, campaign_id=uuid4(), occurred_at=_NOW)
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=1,
        events=[
            to_new_event(
                event_type=event_type_name(added),
                payload=to_payload(added),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="seed",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            ),
        ],
    )

    agent_id = uuid4()
    terminal = _terminal_event(run_id=run_id)
    success, winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )
    assert success is True
    assert winner is None


class _RaceInjectingStore:
    """InMemoryEventStore wrapper that simulates a concurrent appender.

    On the FIRST `append` call, raises `ConcurrencyError` after
    optionally inserting a competing lease event into the underlying
    store (mimicking a winning peer that committed between this
    helper's load and append). Subsequent appends pass through.
    """

    def __init__(
        self,
        delegate: InMemoryEventStore,
        *,
        injected_events: list[NewEvent] | None = None,
        injected_stream_type: str = "Run",
        injected_stream_id: UUID | None = None,
        injected_expected_version: int = 1,
    ) -> None:
        self._delegate = delegate
        self._injected_events = injected_events
        self._injected_stream_type = injected_stream_type
        self._injected_stream_id = injected_stream_id
        self._injected_expected_version = injected_expected_version
        self._first_append_consumed = False

    async def load(
        self,
        stream_type: str,
        stream_id: UUID,
    ) -> tuple[list[StoredEvent], int]:
        return await self._delegate.load(stream_type, stream_id)

    async def append(
        self,
        stream_type: str,
        stream_id: UUID,
        expected_version: int,
        events: Sequence[NewEvent],
    ) -> int:
        if not self._first_append_consumed:
            self._first_append_consumed = True
            if self._injected_events is not None:
                await self._delegate.append(
                    stream_type=self._injected_stream_type,
                    stream_id=self._injected_stream_id or stream_id,
                    expected_version=self._injected_expected_version,
                    events=self._injected_events,
                )
            raise ConcurrencyError(
                stream_type=stream_type,
                stream_id=stream_id,
                expected=expected_version,
                actual=expected_version + 1,
            )
        return await self._delegate.append(
            stream_type=stream_type,
            stream_id=stream_id,
            expected_version=expected_version,
            events=events,
        )

    async def append_streams(
        self,
        streams: Sequence[StreamAppend],
        *,
        conn: object | None = None,
    ) -> dict[UUID, int]:
        return await self._delegate.append_streams(streams, conn=conn)


def _foreign_lease_envelope(
    *,
    run_id: UUID,
    debriefer_agent_id: UUID,
    terminal_event_id: UUID,
) -> NewEvent:
    """Build a `DecisionDebriefRequested` envelope as if a peer subscriber wrote it."""
    return to_new_event(
        event_type="DecisionDebriefRequested",
        payload={
            "run_id": str(run_id),
            "debriefer_agent_id": str(debriefer_agent_id),
            "terminal_event_id": str(terminal_event_id),
            "occurred_at": _NOW.isoformat(),
        },
        occurred_at=_NOW,
        event_id=derive_lease_event_id(
            run_id=run_id,
            debriefer_agent_id=debriefer_agent_id,
            terminal_event_id=terminal_event_id,
        ),
        command_name="ForeignAgent",
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=debriefer_agent_id,
    )


@pytest.mark.unit
async def test_attempt_debrief_lease_concurrency_error_with_foreign_winner_returns_loss() -> None:
    """Append raises `ConcurrencyError`; re-scan finds a competing
    lease from a foreign agent; helper returns `(False, foreign_id)`."""
    base = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(base, run_id)
    terminal = _terminal_event(run_id=run_id)
    foreign_id = uuid4()
    losing_id = uuid4()

    store = _RaceInjectingStore(
        base,
        injected_events=[
            _foreign_lease_envelope(
                run_id=run_id,
                debriefer_agent_id=foreign_id,
                terminal_event_id=terminal.event_id,
            ),
        ],
    )

    success, winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=losing_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert success is False
    assert winner == foreign_id


@pytest.mark.unit
async def test_attempt_debrief_lease_concurrency_error_with_own_lease_returns_success() -> None:
    """Append raises `ConcurrencyError`; re-scan finds THIS agent's own
    prior lease (same-instance duplicate fire); helper returns
    `(True, None)` so the caller proceeds to the LLM."""
    base = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(base, run_id)
    terminal = _terminal_event(run_id=run_id)
    agent_id = uuid4()

    store = _RaceInjectingStore(
        base,
        injected_events=[
            _foreign_lease_envelope(
                run_id=run_id,
                debriefer_agent_id=agent_id,
                terminal_event_id=terminal.event_id,
            ),
        ],
    )

    success, winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert success is True
    assert winner is None


@pytest.mark.unit
async def test_attempt_debrief_lease_concurrency_error_with_no_lease_winner_returns_none() -> None:
    """Append raises `ConcurrencyError`; re-scan finds the version
    advanced by a NON-lease event (e.g., `RunAddedToCampaign`); helper
    returns `(False, None)` so the caller writes a `DebriefConflicted`
    Decision with `winning_agent_id` unidentified."""
    from cora.run.aggregates.run.events import RunAddedToCampaign

    base = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(base, run_id)
    terminal = _terminal_event(run_id=run_id)
    agent_id = uuid4()

    added = RunAddedToCampaign(run_id=run_id, campaign_id=uuid4(), occurred_at=_NOW)
    non_lease_envelope = to_new_event(
        event_type=event_type_name(added),
        payload=to_payload(added),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="Campaign",
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=uuid4(),
    )

    store = _RaceInjectingStore(
        base,
        injected_events=[non_lease_envelope],
    )

    success, winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert success is False
    assert winner is None


@pytest.mark.unit
async def test_attempt_debrief_lease_skips_malformed_lease_payload_missing_winner_field() -> None:
    """A `DecisionDebriefRequested` event whose payload omits
    `debriefer_agent_id` (or carries None) is treated as no-winner by
    the scanner (line 81 continue), so the helper proceeds to append
    its own lease instead of treating the malformed event as a peer.
    Defensive against payload-schema drift."""
    store = InMemoryEventStore()
    run_id = uuid4()
    await _seed_run(store, run_id)
    terminal = _terminal_event(run_id=run_id)

    malformed_envelope = to_new_event(
        event_type="DecisionDebriefRequested",
        payload={
            "run_id": str(run_id),
            "terminal_event_id": str(terminal.event_id),
            "occurred_at": _NOW.isoformat(),
        },
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="Malformed",
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=1,
        events=[malformed_envelope],
    )

    agent_id = uuid4()
    success, winner = await attempt_debrief_lease(
        store,
        run_id=run_id,
        debriefer_agent_id=agent_id,
        terminal_event=terminal,
        occurred_at=_NOW,
        command_name=_COMMAND_NAME,
    )

    assert success is True
    assert winner is None
    stored, _v = await store.load("Run", run_id)
    leases = [e for e in stored if e.event_type == "DecisionDebriefRequested"]
    assert len(leases) == 2  # malformed + new lease both present

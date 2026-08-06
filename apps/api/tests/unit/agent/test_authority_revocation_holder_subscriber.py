"""Tests for the AuthorityRevocationHolder subscriber (kill-switch K3).

Covers the apply path against an in-memory event store: a PolicyGrantRevoked
holds each Running Run the revoked principal drives (Pattern C: load + guard +
authorize + append RunHeld), records one Decision(context=AuthorityRevocationHold)
per run, folds a non-Running / missing / Deny run to HoldDeferred, is kind-blind,
skips when unseeded, and is idempotent on re-delivery (deterministic Decision
ids).
"""

# white-box test of the subscriber internals (private helpers / dispositions);
# the fault-injection fakes proxy the real store via __getattr__, so their
# append() args are dynamically typed.
# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_authority_revocation_holder import (
    AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
    seed_authority_revocation_holder_agent,
)
from cora.agent.subscribers.authority_revocation_holder import (
    AuthorityRevocationHolderSubscriber,
    _derive_decision_id,
    make_authority_revocation_holder_subscriber,
)
from cora.decision.aggregates.decision import (
    DECISION_CONTEXT_AUTHORITY_REVOCATION_HOLD,
    load_decision,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import (
    AllowAllAuthorize,
    Authorize,
    ConcurrencyError,
    Deny,
    FakeClock,
    UUIDv7Generator,
)
from cora.infrastructure.ports.event_store import EventStore, StoredEvent
from cora.run.aggregates.run import (
    HOLD_CAUSE_AUTHORITY_REVOCATION,
    RunCompleted,
    RunHeld,
    RunStarted,
    RunStatus,
    load_run,
)
from cora.run.aggregates.run import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run import (
    to_payload as run_to_payload,
)

_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)


def _kernel(authz: Authorize | None = None) -> Kernel:
    settings = Settings()  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=authz or AllowAllAuthorize(),
    )


class _FakeInvolvementLookup:
    def __init__(self, run_ids: list[UUID]) -> None:
        self._run_ids = run_ids
        self.asked_for: list[UUID] = []

    async def runs_driven_by(self, principal_id: UUID) -> list[UUID]:
        self.asked_for.append(principal_id)
        return self._run_ids


async def _seed_running_run(store: EventStore, *, starter: UUID) -> UUID:
    """Append a RunStarted so the run folds to Running; return its run_id."""
    run_id = uuid4()
    started = RunStarted(
        run_id=run_id,
        name="test run",
        plan_id=uuid4(),
        subject_id=uuid4(),
        occurred_at=_NOW,
    )
    envelope = to_new_event(
        event_type=run_event_type_name(started),
        payload=run_to_payload(started),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="StartRun",
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=starter,
    )
    await store.append("Run", run_id, 0, [envelope])
    return run_id


async def _seed_held_run(store: EventStore, *, starter: UUID) -> UUID:
    """Append RunStarted + RunHeld so the run folds to Held (already contained)."""
    run_id = await _seed_running_run(store, starter=starter)
    held = RunHeld(run_id=run_id, decided_by_decision_id=None, occurred_at=_NOW)
    envelope = to_new_event(
        event_type=run_event_type_name(held),
        payload=run_to_payload(held),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="HoldRun",
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=starter,
    )
    await store.append("Run", run_id, 1, [envelope])
    return run_id


async def _seed_completed_run(store: EventStore, *, starter: UUID) -> UUID:
    """Append RunStarted + RunCompleted so the run folds to a terminal status."""
    run_id = await _seed_running_run(store, starter=starter)
    completed = RunCompleted(run_id=run_id, occurred_at=_NOW)
    envelope = to_new_event(
        event_type=run_event_type_name(completed),
        payload=run_to_payload(completed),
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name="CompleteRun",
        correlation_id=uuid4(),
        causation_id=None,
        principal_id=starter,
    )
    await store.append("Run", run_id, 1, [envelope])
    return run_id


def _revocation_event(*, revoked_principal_id: UUID) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Policy",
        stream_id=uuid4(),
        version=1,
        event_type="PolicyGrantRevoked",
        schema_version=1,
        payload={
            "policy_id": str(uuid4()),
            "principal_id": str(revoked_principal_id),
            "revoked_by": str(uuid4()),
            "reason": "trust withdrawn",
            "occurred_at": _NOW.isoformat(),
        },
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


def _build(
    kernel: Kernel,
    *,
    run_ids: list[UUID],
    lookup: _FakeInvolvementLookup | None = None,
) -> AuthorityRevocationHolderSubscriber:
    return AuthorityRevocationHolderSubscriber(
        event_store=kernel.event_store,
        run_actor_involvement_lookup=lookup or _FakeInvolvementLookup(run_ids),
        authz=kernel.authz,
        clock=kernel.clock,
        id_generator=kernel.id_generator,
    )


@pytest.mark.unit
async def test_holds_each_running_run_and_records_held_decision() -> None:
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    run_a = await _seed_running_run(kernel.event_store, starter=revoked)
    run_b = await _seed_running_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[run_a, run_b])

    event = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    for run_id in (run_a, run_b):
        state = await load_run(kernel.event_store, run_id)
        assert state is not None
        assert state.status is RunStatus.HELD

    for run_id in (run_a, run_b):
        decision = await load_decision(
            kernel.event_store, _derive_decision_id(event.event_id, run_id)
        )
        assert decision is not None
        assert decision.context.value == DECISION_CONTEXT_AUTHORITY_REVOCATION_HOLD
        assert decision.choice.value == "Held"
        assert decision.parent_id == event.event_id
        assert decision.decided_by == AUTHORITY_REVOCATION_HOLDER_AGENT_ID


@pytest.mark.unit
async def test_asks_lookup_for_the_revoked_principal() -> None:
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    lookup = _FakeInvolvementLookup([])
    sub = _build(kernel, run_ids=[], lookup=lookup)

    await sub.apply(_revocation_event(revoked_principal_id=revoked), conn=None)  # type: ignore[arg-type]

    assert lookup.asked_for == [revoked]


@pytest.mark.unit
async def test_already_held_run_still_records_the_revocation_claim() -> None:
    """The safety fix. A run held by ANOTHER concern must still take the
    kill-switch's claim: deferring wrote a Decision but no Run event, so the other
    concern's release resumed the run with the revocation unenforced."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    run_id = await _seed_held_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[run_id])

    event = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.HELD
    assert HOLD_CAUSE_AUTHORITY_REVOCATION in [cause for _, cause in state.hold_claims]
    decision = await load_decision(kernel.event_store, _derive_decision_id(event.event_id, run_id))
    assert decision is not None
    assert decision.choice.value == "Held"


@pytest.mark.unit
async def test_run_already_held_by_this_killswitch_folds_to_hold_deferred() -> None:
    """Re-delivery is idempotent: the derived claim is already active, so the
    second delivery records HoldDeferred and appends no second RunHeld."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[run_id])

    first = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(first, conn=None)  # type: ignore[arg-type]
    second = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(second, conn=None)  # type: ignore[arg-type]

    stored, _ = await kernel.event_store.load("Run", run_id)
    assert sum(1 for e in stored if e.event_type == "RunHeld") == 1
    decision = await load_decision(kernel.event_store, _derive_decision_id(second.event_id, run_id))
    assert decision is not None
    assert decision.choice.value == "HoldDeferred"


@pytest.mark.unit
async def test_missing_run_folds_to_hold_deferred() -> None:
    """A stale involvement row (run id with no stream) records HoldDeferred, no crash."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    ghost_run = uuid4()  # never seeded
    sub = _build(kernel, run_ids=[ghost_run])

    event = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    decision = await load_decision(
        kernel.event_store, _derive_decision_id(event.event_id, ghost_run)
    )
    assert decision is not None
    assert decision.choice.value == "HoldDeferred"


@pytest.mark.unit
async def test_authorize_deny_folds_to_hold_deferred() -> None:
    """When Authorize denies HoldRun, the run is NOT held and the holder records
    HoldDeferred (degrade safe, no crash)."""

    class _DenyAll:
        async def authorize(
            self, *, principal_id: UUID, command_name: str, conduit_id: UUID, surface_id: UUID
        ) -> Deny:
            _ = (principal_id, command_name, conduit_id, surface_id)
            return Deny(reason="not permitted")

    kernel = _kernel(authz=_DenyAll())  # type: ignore[arg-type]
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[run_id])

    event = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.RUNNING  # not held: authz denied
    decision = await load_decision(kernel.event_store, _derive_decision_id(event.event_id, run_id))
    assert decision is not None
    assert decision.choice.value == "HoldDeferred"


@pytest.mark.unit
async def test_no_in_flight_runs_writes_no_decision() -> None:
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    sub = _build(kernel, run_ids=[])

    event = _revocation_event(revoked_principal_id=uuid4())
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    assert (
        await load_decision(kernel.event_store, _derive_decision_id(event.event_id, uuid4()))
        is None
    )


@pytest.mark.unit
async def test_unseeded_holder_stands_down() -> None:
    """Before the bootstrap seed runs, the holder resolves no Actor and does not act."""
    kernel = _kernel()  # NOT seeded
    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[run_id])

    await sub.apply(_revocation_event(revoked_principal_id=revoked), conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.RUNNING  # untouched


@pytest.mark.unit
async def test_redelivery_is_idempotent() -> None:
    """Re-applying the same revocation holds once and records one Held Decision: the
    second delivery sees status=Held -> HoldDeferred disposition, but the Decision
    id is deterministic so the earlier Held Decision survives (ConcurrencyError
    no-op) and only one RunHeld lands on the stream."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[run_id])

    event = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(event, conn=None)  # type: ignore[arg-type]
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    stored, _version = await kernel.event_store.load("Run", run_id)
    held_count = sum(1 for s in stored if s.event_type == "RunHeld")
    assert held_count == 1
    decision = await load_decision(kernel.event_store, _derive_decision_id(event.event_id, run_id))
    assert decision is not None
    assert decision.choice.value == "Held"


@pytest.mark.unit
async def test_ignores_non_trigger_event_types() -> None:
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[run_id])

    other = _revocation_event(revoked_principal_id=revoked)
    object.__setattr__(other, "event_type", "PolicyGrantAdded")
    await sub.apply(other, conn=None)  # type: ignore[arg-type]

    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.RUNNING  # untouched


@pytest.mark.unit
async def test_mixed_fan_out_continues_past_a_deferred_run() -> None:
    """A deferred run (terminal) must not stop the loop: a Running sibling is
    still held. Pins per-run independence in the fan-out.

    Uses a COMPLETED run as the deferred case. An already-Held run is no longer
    deferred: it takes the revocation claim like any other."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    terminal = await _seed_completed_run(kernel.event_store, starter=revoked)
    running = await _seed_running_run(kernel.event_store, starter=revoked)
    sub = _build(kernel, run_ids=[terminal, running])

    event = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    held_decision = await load_decision(
        kernel.event_store, _derive_decision_id(event.event_id, terminal)
    )
    running_decision = await load_decision(
        kernel.event_store, _derive_decision_id(event.event_id, running)
    )
    assert held_decision is not None and held_decision.choice.value == "HoldDeferred"
    assert running_decision is not None and running_decision.choice.value == "Held"
    running_state = await load_run(kernel.event_store, running)
    assert running_state is not None and running_state.status is RunStatus.HELD


@pytest.mark.unit
async def test_one_run_failure_does_not_abandon_siblings() -> None:
    """If holding one run raises, the loop isolates it and still holds the rest
    (the kill-switch must not silently drop siblings). Simulated by an event store
    whose Decision append raises once for a chosen run's Decision id."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    boom_run = await _seed_running_run(kernel.event_store, starter=revoked)
    ok_run = await _seed_running_run(kernel.event_store, starter=revoked)

    event = _revocation_event(revoked_principal_id=revoked)
    boom_decision_id = _derive_decision_id(event.event_id, boom_run)
    real_store = kernel.event_store
    raised = {"done": False}

    class _FlakyStore:
        def __getattr__(self, name: str) -> object:
            return getattr(real_store, name)

        async def append(self, stream_type, stream_id, expected_version, events):  # type: ignore[no-untyped-def]
            if stream_type == "Decision" and stream_id == boom_decision_id and not raised["done"]:
                raised["done"] = True
                raise RuntimeError("transient decision-append fault")
            return await real_store.append(stream_type, stream_id, expected_version, events)

    sub = AuthorityRevocationHolderSubscriber(
        event_store=_FlakyStore(),  # type: ignore[arg-type]
        run_actor_involvement_lookup=_FakeInvolvementLookup([boom_run, ok_run]),
        authz=kernel.authz,
        clock=kernel.clock,
        id_generator=kernel.id_generator,
    )
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    # The sibling was still held despite the first run's fault.
    ok_state = await load_run(kernel.event_store, ok_run)
    assert ok_state is not None and ok_state.status is RunStatus.HELD


@pytest.mark.unit
async def test_lost_concurrency_race_folds_to_hold_deferred() -> None:
    """If the Run advances between the load and the RunHeld append, the append's
    ConcurrencyError is caught and recorded as HoldDeferred, not raised."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    real_store = kernel.event_store

    class _RaceStore:
        def __getattr__(self, name: str) -> object:
            return getattr(real_store, name)

        async def append(self, stream_type, stream_id, expected_version, events):  # type: ignore[no-untyped-def]
            if stream_type == "Run":
                raise ConcurrencyError(
                    stream_type=stream_type,
                    stream_id=stream_id,
                    expected=expected_version,
                    actual=expected_version + 1,
                )
            return await real_store.append(stream_type, stream_id, expected_version, events)

    sub = AuthorityRevocationHolderSubscriber(
        event_store=_RaceStore(),  # type: ignore[arg-type]
        run_actor_involvement_lookup=_FakeInvolvementLookup([run_id]),
        authz=kernel.authz,
        clock=kernel.clock,
        id_generator=kernel.id_generator,
    )
    event = _revocation_event(revoked_principal_id=revoked)
    await sub.apply(event, conn=None)  # type: ignore[arg-type]

    decision = await load_decision(kernel.event_store, _derive_decision_id(event.event_id, run_id))
    assert decision is not None
    assert decision.choice.value == "HoldDeferred"


@pytest.mark.unit
async def test_malformed_payload_is_swallowed_not_wedged() -> None:
    """A PolicyGrantRevoked missing principal_id raises inside _handle_revocation;
    apply() swallows it (logged skip) so the shared bookmark is never wedged."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    sub = _build(kernel, run_ids=[])

    event = _revocation_event(revoked_principal_id=uuid4())
    object.__setattr__(event, "payload", {"policy_id": str(uuid4())})  # no principal_id
    # Must not raise.
    await sub.apply(event, conn=None)  # type: ignore[arg-type]


@pytest.mark.unit
def test_decision_id_distinct_across_revocations_of_same_run() -> None:
    """Two distinct revocation events targeting the same run derive distinct
    Decision ids, so a later revocation is not swallowed as a re-delivery of an
    earlier one (the derivation keys on the event id, not the principal)."""
    run_id = uuid4()
    first = _derive_decision_id(uuid4(), run_id)
    second = _derive_decision_id(uuid4(), run_id)
    assert first != second


@pytest.mark.unit
async def test_make_subscriber_from_kernel_wires_deps() -> None:
    kernel = _kernel()
    sub = make_authority_revocation_holder_subscriber(kernel)
    assert sub.name == "authority_revocation_holder"
    assert sub.subscribed_event_types == frozenset({"PolicyGrantRevoked", "ActorDeactivated"})
    assert sub.batch_size == 1


def _deactivation_event(*, deactivated_actor_id: UUID) -> StoredEvent:
    """The second withdrawal gesture, which names the principal `actor_id`."""
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Actor",
        stream_id=deactivated_actor_id,
        version=2,
        event_type="ActorDeactivated",
        schema_version=1,
        payload={
            "actor_id": str(deactivated_actor_id),
            "occurred_at": _NOW.isoformat(),
        },
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


@pytest.mark.unit
async def test_deactivating_a_principal_holds_the_runs_it_drives() -> None:
    """The gap this subscription closes.

    Revoking a grant paused a principal's runs; deactivating them, the more
    total gesture, left the same runs going. Both mean "may no longer drive
    this", so both must pause the work. Asserted through the identical path
    the revocation trigger uses, because the whole point of widening the
    existing subscriber rather than writing a sibling is that the careful
    parts stay shared.
    """
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    deactivated = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=deactivated)
    sub = _build(kernel, run_ids=[run_id])

    await sub.apply(
        _deactivation_event(deactivated_actor_id=deactivated),
        conn=None,  # type: ignore[arg-type]
    )

    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.HELD


@pytest.mark.unit
async def test_deactivation_trigger_reads_actor_id_not_principal_id() -> None:
    """The two gestures name the principal differently.

    `PolicyGrantRevoked` carries `principal_id`; `ActorDeactivated` carries
    `actor_id`. Reading the wrong key would raise a KeyError inside the
    reaction and drop the kill-switch on the floor, so the field map is
    pinned by asking the lookup what it was actually given.
    """
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)
    deactivated = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=deactivated)
    lookup = _FakeInvolvementLookup([run_id])
    sub = _build(kernel, run_ids=[run_id], lookup=lookup)

    await sub.apply(
        _deactivation_event(deactivated_actor_id=deactivated),
        conn=None,  # type: ignore[arg-type]
    )

    assert lookup.asked_for == [deactivated]

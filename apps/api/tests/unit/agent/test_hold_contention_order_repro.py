"""REGRESSION: hold contention between the consequence gate and the kill-switch
must not depend on the order the two holds arrive in.

The fault this file pins. Both holders used to guard `status is RUNNING` and fold
a non-Running run to a no-op, so a hold arriving at an ALREADY-HELD run appended
nothing to the Run stream. The release guard then scanned backward for the latest
`RunHeld` and compared its envelope principal, which answers "did I place the most
recent hold" -- the right question only when holds cannot overlap. The dropped
hold left no event for it to find.

That made the outcome order-dependent:

  - Order A, kill-switch holds first: the gate's hold is dropped, the latest
    RunHeld is the kill-switch's, the grant does not resume. Correct, and the only
    order the suite covered (`test_release_does_not_clear_a_foreign_hold`).
  - Order B, gate holds first and the revocation arrives during the co-signature
    wait: the REVOCATION is dropped, the latest RunHeld is the gate's own, and the
    grant resumes the run with the revocation unenforced. The window is a human
    co-signature wait, so it is wide by design, and the kill-switch never fires
    again (one PolicyGrantRevoked, idempotent re-delivery, no sweep).

Cause-scoped claims fix it: each concern records its own claim, and a release
discharges only its own and resumes only when no claim remains. These tests drive
both orders end to end through the REAL subscribers, plus the reversibility case
(clearing the last claim still resumes) and the operator refusal.
"""

# white-box reproduction: same posture as the two subscriber test modules it draws on
# pyright: reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_authority_revocation_holder import (
    AUTHORITY_REVOCATION_HOLDER_AGENT_ID,
    seed_authority_revocation_holder_agent,
)
from cora.agent.seed_ratification_enforcer import (
    RATIFICATION_ENFORCER_AGENT_ID,
    seed_ratification_enforcer_agent,
)
from cora.agent.subscribers.authority_revocation_holder import (
    AuthorityRevocationHolderSubscriber,
)
from cora.agent.subscribers.ratification_hold import make_ratification_hold_subscriber
from cora.agent.subscribers.ratification_release import make_ratification_release_subscriber
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.ports.event_store import EventStore, StoredEvent
from cora.run.aggregates.run import (
    HOLD_CAUSE_AUTHORITY_REVOCATION,
    HOLD_CAUSE_OPERATOR,
    HOLD_CAUSE_RATIFICATION,
    RunHoldClaimsRemainError,
    RunStarted,
    RunStatus,
    load_run,
)
from cora.run.aggregates.run import event_type_name as run_event_type_name
from cora.run.aggregates.run import to_payload as run_to_payload
from cora.run.features.resume_run.command import ResumeRun
from cora.run.features.resume_run.decider import decide as resume_decide
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


class _FakeInvolvementLookup:
    """K2 stand-in: the revoked principal drives exactly these runs."""

    def __init__(self, run_ids: list[UUID]) -> None:
        self._run_ids = run_ids

    async def runs_driven_by(self, principal_id: UUID) -> list[UUID]:
        _ = principal_id
        return self._run_ids


async def _seed_running_run(store: EventStore, *, starter: UUID) -> UUID:
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
                principal_id=starter,
            )
        ],
    )
    return run_id


async def _seed_ratification(store: EventStore, *, target_run_id: UUID) -> UUID:
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


def _requested_event(*, ratification_id: UUID, target_run_id: UUID) -> StoredEvent:
    return StoredEvent(
        position=1,
        event_id=uuid4(),
        stream_type="Ratification",
        stream_id=ratification_id,
        version=1,
        event_type="RatificationRequested",
        schema_version=1,
        payload={
            "ratification_id": str(ratification_id),
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


def _revocation_holder(kernel: Kernel, run_ids: list[UUID]) -> AuthorityRevocationHolderSubscriber:
    return AuthorityRevocationHolderSubscriber(
        event_store=kernel.event_store,
        run_actor_involvement_lookup=_FakeInvolvementLookup(run_ids),  # type: ignore[arg-type]
        authz=kernel.authz,
        clock=kernel.clock,
        id_generator=kernel.id_generator,
    )


async def _hold_principals(kernel: Kernel, run_id: UUID) -> list[UUID | None]:
    stored, _ = await kernel.event_store.load("Run", run_id)
    return [s.principal_id for s in stored if s.event_type == "RunHeld"]


async def _resume_count(kernel: Kernel, run_id: UUID) -> int:
    stored, _ = await kernel.event_store.load("Run", run_id)
    return sum(1 for s in stored if s.event_type == "RunResumed")


async def _claim_release_count(kernel: Kernel, run_id: UUID) -> int:
    stored, _ = await kernel.event_store.load("Run", run_id)
    return sum(1 for s in stored if s.event_type == "HoldClaimReleased")


# --------------------------------------------------------------------------
# Order A -- the covered order. Kill-switch holds first.
# --------------------------------------------------------------------------


@pytest.mark.unit
async def test_order_a_killswitch_first_foreign_hold_survives() -> None:
    """Control. Revocation holds, THEN the co-signature is granted: no resume."""
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    await seed_authority_revocation_holder_agent(kernel)

    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    ratification_id = await _seed_ratification(kernel.event_store, target_run_id=run_id)

    # 1. kill-switch holds the revoked principal's in-flight run
    await _revocation_holder(kernel, [run_id]).apply(
        _revocation_event(revoked_principal_id=revoked),
        conn=None,  # type: ignore[arg-type]
    )
    # 2. consequence gate tries to hold the same run -- already Held, no-op
    await make_ratification_hold_subscriber(kernel).apply(
        _requested_event(ratification_id=ratification_id, target_run_id=run_id),
        conn=None,  # type: ignore[arg-type]
    )
    # 3. co-signature granted -> release attempts a resume
    await make_ratification_release_subscriber(kernel).apply(
        _granted_event(ratification_id=ratification_id),
        conn=None,  # type: ignore[arg-type]
    )

    holds = await _hold_principals(kernel, run_id)
    assert holds == [AUTHORITY_REVOCATION_HOLDER_AGENT_ID, RATIFICATION_ENFORCER_AGENT_ID]
    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.HELD, "kill-switch hold must survive the grant"
    assert [cause for _, cause in state.hold_claims] == [HOLD_CAUSE_AUTHORITY_REVOCATION]
    assert await _resume_count(kernel, run_id) == 0


# --------------------------------------------------------------------------
# Order B -- the uncovered order. Consequence gate holds first, revocation
# arrives during the co-signature wait.
# --------------------------------------------------------------------------


@pytest.mark.unit
async def test_order_b_revocation_during_cosignature_wait_keeps_run_held() -> None:
    """The regression. Consequence gate holds, revocation arrives while the run
    is Held, then the co-signature is granted.

    Before cause-scoped claims: the revocation's hold folded to HoldDeferred and
    appended nothing, the only RunHeld was the enforcer's own, and the grant
    resumed the run with the revocation unenforced.

    After: the revocation records its own claim on the already-held run, and the
    grant discharges only the ratification claim, so the run stays Held.
    """
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    await seed_authority_revocation_holder_agent(kernel)

    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    ratification_id = await _seed_ratification(kernel.event_store, target_run_id=run_id)

    # 1. consequence gate holds the run pending co-signature
    await make_ratification_hold_subscriber(kernel).apply(
        _requested_event(ratification_id=ratification_id, target_run_id=run_id),
        conn=None,  # type: ignore[arg-type]
    )
    held_after_gate = await load_run(kernel.event_store, run_id)
    assert held_after_gate is not None and held_after_gate.status is RunStatus.HELD

    # 2. the principal's authority is revoked DURING the wait (a long window by
    #    design: the wait is a human co-signature)
    await _revocation_holder(kernel, [run_id]).apply(
        _revocation_event(revoked_principal_id=revoked),
        conn=None,  # type: ignore[arg-type]
    )

    # The kill-switch now records its claim on the already-held run.
    holds = await _hold_principals(kernel, run_id)
    assert holds == [RATIFICATION_ENFORCER_AGENT_ID, AUTHORITY_REVOCATION_HOLDER_AGENT_ID], (
        f"expected both holds on the stream, got {holds}"
    )
    both = await load_run(kernel.event_store, run_id)
    assert both is not None
    assert [cause for _, cause in both.hold_claims] == [
        HOLD_CAUSE_RATIFICATION,
        HOLD_CAUSE_AUTHORITY_REVOCATION,
    ]

    # 3. co-signature granted -> gate discharges ONLY its own claim
    await make_ratification_release_subscriber(kernel).apply(
        _granted_event(ratification_id=ratification_id),
        conn=None,  # type: ignore[arg-type]
    )

    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.HELD, (
        "the revocation's hold must survive the co-signature grant"
    )
    assert [cause for _, cause in state.hold_claims] == [HOLD_CAUSE_AUTHORITY_REVOCATION]
    assert await _resume_count(kernel, run_id) == 0
    assert await _claim_release_count(kernel, run_id) == 1


@pytest.mark.unit
async def test_order_b_resumes_once_the_revocation_claim_is_also_cleared() -> None:
    """The hold stays reversible: clearing the last claim resumes the run.

    Guards against over-correcting into a run that can never resume. The
    operator's ResumeRun discharges the revocation claim, and because it is then
    the only one active, the run returns to Running.
    """
    kernel = _kernel()
    await seed_ratification_enforcer_agent(kernel)
    await seed_authority_revocation_holder_agent(kernel)

    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    ratification_id = await _seed_ratification(kernel.event_store, target_run_id=run_id)

    await make_ratification_hold_subscriber(kernel).apply(
        _requested_event(ratification_id=ratification_id, target_run_id=run_id),
        conn=None,  # type: ignore[arg-type]
    )
    await _revocation_holder(kernel, [run_id]).apply(
        _revocation_event(revoked_principal_id=revoked),
        conn=None,  # type: ignore[arg-type]
    )
    await make_ratification_release_subscriber(kernel).apply(
        _granted_event(ratification_id=ratification_id),
        conn=None,  # type: ignore[arg-type]
    )

    # Only the revocation claim remains; discharging it resumes the run.
    state = await load_run(kernel.event_store, run_id)
    assert state is not None
    events = resume_decide(
        state,
        ResumeRun(run_id=run_id, cause=HOLD_CAUSE_AUTHORITY_REVOCATION),
        now=_NOW,
    )
    assert [type(e).__name__ for e in events] == ["RunResumed"]


@pytest.mark.unit
async def test_operator_cannot_resume_past_a_revocation_hold() -> None:
    """An operator resuming a run held by the kill-switch is refused, and told
    which concern is holding it."""
    kernel = _kernel()
    await seed_authority_revocation_holder_agent(kernel)

    revoked = uuid4()
    run_id = await _seed_running_run(kernel.event_store, starter=revoked)
    await _revocation_holder(kernel, [run_id]).apply(
        _revocation_event(revoked_principal_id=revoked),
        conn=None,  # type: ignore[arg-type]
    )

    state = await load_run(kernel.event_store, run_id)
    assert state is not None and state.status is RunStatus.HELD
    with pytest.raises(RunHoldClaimsRemainError) as excinfo:
        resume_decide(state, ResumeRun(run_id=run_id, cause=HOLD_CAUSE_OPERATOR), now=_NOW)
    assert excinfo.value.blocking_causes == (HOLD_CAUSE_AUTHORITY_REVOCATION,)

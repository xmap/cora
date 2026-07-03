"""Unit tests for AuthorityRevocationHolderSubscriber (the kill-switch).

Drives the subscriber with fakes: a seedable in-memory involvement
lookup, an AsyncMock event_store (the Decision append) and hold_run
handler, a fixed clock + id generator. Postgres-side end-to-end behavior
(the real projection + TrustAuthorize gate) is the E4 integration
scenario.

Pins:
  - One Decision + one HoldRun per in-flight run the revoked actor is behind.
  - Both are keyed to SYSTEM_PRINCIPAL_ID (no bespoke agent identity).
  - Empty lookup -> no Decision, no hold.
  - ConcurrencyError on the Decision append (already processed) -> no hold.
  - RunCannotHoldError / RunNotFoundError from hold_run -> swallowed.
  - A malformed event never raises out of apply (bookmark must not wedge).
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports import ConcurrencyError
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.run.aggregates.run.state import RunCannotHoldError, RunNotFoundError
from cora.run.ports import InMemoryRunActorInvolvementLookup
from cora.run.subscribers import AuthorityRevocationHolderSubscriber

_NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=UTC)
_REVOKED_PRINCIPAL = UUID("01900000-0000-7000-8000-0000feed0001")
_POLICY_ID = UUID("01900000-0000-7000-8000-0000feed0002")
_EVENT_ID = UUID("01900000-0000-7000-8000-0000feed0003")


class _SeqIdGenerator:
    """Deterministic IdGenerator stub: a fresh uuid4 each call."""

    def new_id(self) -> UUID:
        return uuid4()


def _clock() -> Any:
    return SimpleNamespace(now=lambda: _NOW)


def _event(
    *,
    revoked_principal_id: UUID = _REVOKED_PRINCIPAL,
    policy_id: UUID | None = _POLICY_ID,
    event_type: str = "PolicyGrantRevoked",
) -> StoredEvent:
    payload: dict[str, Any] = {"revoked_principal_id": str(revoked_principal_id)}
    if policy_id is not None:
        payload["policy_id"] = str(policy_id)
    payload["reason"] = "agent decommissioned"
    payload["occurred_at"] = _NOW.isoformat()
    return StoredEvent(
        position=1,
        event_id=_EVENT_ID,
        stream_type="Policy",
        stream_id=_POLICY_ID,
        version=2,
        event_type=event_type,
        schema_version=1,
        payload=payload,
        correlation_id=uuid4(),
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


def _make_subscriber(
    *,
    inflight_run_ids: set[UUID] | None = None,
    event_store: Any = None,
    hold_run: Any = None,
) -> AuthorityRevocationHolderSubscriber:
    lookup = InMemoryRunActorInvolvementLookup()
    for run_id in inflight_run_ids or set():
        lookup.register(actor_id=_REVOKED_PRINCIPAL, run_id=run_id)
    return AuthorityRevocationHolderSubscriber(
        event_store=event_store if event_store is not None else AsyncMock(),
        hold_run=hold_run if hold_run is not None else AsyncMock(),
        involvement_lookup=lookup,
        clock=_clock(),
        id_generator=_SeqIdGenerator(),
    )


@pytest.mark.unit
def test_subscriber_metadata() -> None:
    assert AuthorityRevocationHolderSubscriber.name == "authority_revocation_holder"
    assert AuthorityRevocationHolderSubscriber.subscribed_event_types == frozenset(
        {"PolicyGrantRevoked"}
    )
    assert AuthorityRevocationHolderSubscriber.batch_size == 1


@pytest.mark.unit
async def test_holds_each_inflight_run_as_system() -> None:
    run_a, run_b = uuid4(), uuid4()
    event_store = AsyncMock()
    hold_run = AsyncMock()
    sub = _make_subscriber(
        inflight_run_ids={run_a, run_b}, event_store=event_store, hold_run=hold_run
    )

    await sub.apply(_event(), conn=None)

    # One Decision appended + one HoldRun issued per in-flight run.
    assert event_store.append.await_count == 2
    assert hold_run.await_count == 2
    # Every Decision append is on the Decision stream, principal = SYSTEM.
    for call in event_store.append.await_args_list:
        assert call.kwargs["stream_type"] == "Decision"
        assert call.kwargs["expected_version"] == 0
    # Every HoldRun is issued as SYSTEM_PRINCIPAL_ID.
    for call in hold_run.await_args_list:
        assert call.kwargs["principal_id"] == SYSTEM_PRINCIPAL_ID
    held_run_ids = {call.args[0].run_id for call in hold_run.await_args_list}
    assert held_run_ids == {run_a, run_b}


@pytest.mark.unit
async def test_no_inflight_runs_is_noop() -> None:
    event_store = AsyncMock()
    hold_run = AsyncMock()
    sub = _make_subscriber(inflight_run_ids=set(), event_store=event_store, hold_run=hold_run)

    await sub.apply(_event(), conn=None)

    event_store.append.assert_not_awaited()
    hold_run.assert_not_awaited()


@pytest.mark.unit
async def test_hold_is_linked_to_the_recorded_decision() -> None:
    run_id = uuid4()
    event_store = AsyncMock()
    hold_run = AsyncMock()
    sub = _make_subscriber(inflight_run_ids={run_id}, event_store=event_store, hold_run=hold_run)

    await sub.apply(_event(), conn=None)

    # The HoldRun carries decided_by_decision_id = the Decision stream id
    # that was appended (the audit linkage).
    decision_stream_id = event_store.append.await_args_list[0].kwargs["stream_id"]
    hold_command = hold_run.await_args_list[0].args[0]
    assert hold_command.decided_by_decision_id == decision_stream_id


@pytest.mark.unit
async def test_concurrency_error_on_decision_skips_hold() -> None:
    """If the Decision was already written (re-delivery), do not re-issue hold."""
    run_id = uuid4()
    event_store = AsyncMock()
    event_store.append.side_effect = ConcurrencyError(
        stream_type="Decision", stream_id=uuid4(), expected=0, actual=1
    )
    hold_run = AsyncMock()
    sub = _make_subscriber(inflight_run_ids={run_id}, event_store=event_store, hold_run=hold_run)

    await sub.apply(_event(), conn=None)

    hold_run.assert_not_awaited()


@pytest.mark.unit
async def test_hold_state_race_not_found_is_swallowed() -> None:
    """A run gone between lookup and issue is a benign no-op, not a raise."""
    run_id = uuid4()
    hold_run = AsyncMock()
    hold_run.side_effect = RunNotFoundError(run_id)
    sub = _make_subscriber(inflight_run_ids={run_id}, hold_run=hold_run)

    await sub.apply(_event(), conn=None)  # must not raise
    hold_run.assert_awaited_once()


@pytest.mark.unit
async def test_hold_state_race_cannot_hold_is_swallowed() -> None:
    """A run already Held / terminal is a benign no-op, not a raise."""
    from cora.run.aggregates.run.state import RunStatus

    run_id = uuid4()
    hold_run = AsyncMock()
    hold_run.side_effect = RunCannotHoldError(run_id, RunStatus.HELD)
    sub = _make_subscriber(inflight_run_ids={run_id}, hold_run=hold_run)

    await sub.apply(_event(), conn=None)  # must not raise
    hold_run.assert_awaited_once()


@pytest.mark.unit
async def test_wrong_event_type_is_ignored() -> None:
    event_store = AsyncMock()
    hold_run = AsyncMock()
    sub = _make_subscriber(inflight_run_ids={uuid4()}, event_store=event_store, hold_run=hold_run)

    await sub.apply(_event(event_type="PolicyDefined"), conn=None)

    event_store.append.assert_not_awaited()
    hold_run.assert_not_awaited()


@pytest.mark.unit
async def test_malformed_event_never_raises() -> None:
    """A payload missing revoked_principal_id must not wedge the bookmark."""
    event_store = AsyncMock()
    hold_run = AsyncMock()
    sub = _make_subscriber(inflight_run_ids={uuid4()}, event_store=event_store, hold_run=hold_run)
    bad = _event()
    object.__setattr__(bad, "payload", {"occurred_at": _NOW.isoformat()})  # drop keys

    # Must swallow the KeyError inside apply.
    await sub.apply(bad, conn=None)
    hold_run.assert_not_awaited()

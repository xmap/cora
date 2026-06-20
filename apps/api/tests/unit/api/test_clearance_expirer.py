"""Tests for the ClearanceExpirer runtime (cora.api._clearance_expirer).

Covers the pure rule (is_window_elapsed) on both sides of the inclusive
boundary, plus a fakes-driven tick that exercises the full select -> authorized
expire_clearance -> Decision loop, every swallowed race/exception arm, the
Actor.active revocation gate, pagination, and the disabled no-op.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_clearance_expirer import (
    CLEARANCE_EXPIRER_AGENT_ID,
    seed_clearance_expirer_agent,
)
from cora.api._clearance_expirer import (
    _derive_decision_id,
    clearance_expirer_lifespan,
    is_window_elapsed,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance import (
    ClearanceCannotExpireError,
    ClearanceNotFoundError,
    ClearanceStatus,
    InvalidClearanceExpireReasonError,
)
from cora.safety.errors import UnauthorizedError
from cora.safety.features.expire_clearance import ExpireClearance
from cora.safety.features.list_clearances import (
    ClearanceListPage,
    ClearanceSummaryItem,
    ListClearances,
)
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
_PAST = _NOW - timedelta(hours=1)
_FUTURE = _NOW + timedelta(hours=1)


# ---------- pure rule: is_window_elapsed ----------


@pytest.mark.unit
def test_window_elapsed_when_valid_until_in_past() -> None:
    assert is_window_elapsed(_PAST, _NOW) is True


@pytest.mark.unit
def test_window_not_elapsed_when_valid_until_in_future() -> None:
    assert is_window_elapsed(_FUTURE, _NOW) is False


@pytest.mark.unit
def test_window_elapsed_is_inclusive_at_boundary() -> None:
    """valid_until == now EXPIRES (inclusive <=); pins the `<`-vs-`<=` mutant."""
    assert is_window_elapsed(_NOW, _NOW) is True


@pytest.mark.unit
def test_window_never_elapsed_when_indefinite() -> None:
    assert is_window_elapsed(None, _NOW) is False


# ---------- tick: full loop with fakes ----------


def _kernel(*, enabled: bool = False) -> Kernel:
    settings = Settings(clearance_expirer_enabled=enabled)  # type: ignore[call-arg]
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _item(
    clearance_id: UUID, *, valid_until: datetime | None, status: str = "Active"
) -> ClearanceSummaryItem:
    return ClearanceSummaryItem(
        clearance_id=clearance_id,
        template_id=uuid4(),
        template_code="ESAF",
        facility_code="aps",
        title="2-BM beamtime safety approval",
        external_id=None,
        status=status,
        risk_band="Green",
        subject_binding_ids=[],
        asset_binding_ids=[],
        run_binding_ids=[],
        procedure_binding_ids=[],
        parent_id=None,
        registered_at=_PAST,
        last_status_changed_at=None,
        last_status_reason=None,
        last_reviewed_by=None,
        valid_from=None,
        valid_until=valid_until,
        next_review_due_at=None,
    )


def _make_list_clearances(active: list[ClearanceSummaryItem]):
    async def list_clearances(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage:
        items = active if query.status == "Active" else []
        return ClearanceListPage(items=items, next_cursor=None)

    return list_clearances


def _make_recording_expire():
    calls: list[ExpireClearance] = []

    async def expire_clearance(
        command: ExpireClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        calls.append(command)

    return expire_clearance, calls


def _make_raising_expire(exc: Exception):
    async def expire_clearance(
        command: ExpireClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> None:
        raise exc

    return expire_clearance


@pytest.mark.unit
async def test_tick_expires_elapsed_clearance_and_records_decision() -> None:
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances([_item(cid, valid_until=_PAST)])
    expire_clearance, calls = _make_recording_expire()

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert len(calls) == 1
    assert calls[0].clearance_id == cid
    assert calls[0].reason

    decision = await load_decision(kernel.event_store, _derive_decision_id(cid))
    assert decision is not None
    assert decision.context.value == "ClearanceExpiry"
    assert decision.choice.value == "Expire"
    assert decision.decided_by == ActorId(CLEARANCE_EXPIRER_AGENT_ID)


@pytest.mark.unit
async def test_tick_skips_clearance_with_future_window() -> None:
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances([_item(cid, valid_until=_FUTURE)])
    expire_clearance, calls = _make_recording_expire()

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert calls == []
    assert await load_decision(kernel.event_store, _derive_decision_id(cid)) is None


@pytest.mark.unit
async def test_tick_skips_indefinite_clearance() -> None:
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances([_item(cid, valid_until=None)])
    expire_clearance, calls = _make_recording_expire()

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert calls == []


@pytest.mark.unit
async def test_tick_is_noop_when_expirer_actor_absent() -> None:
    """Revocation gate: with no seeded (active) ClearanceExpirer Actor, do nothing."""
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()  # NOT seeded
    list_clearances = _make_list_clearances([_item(uuid4(), valid_until=_PAST)])
    expire_clearance, calls = _make_recording_expire()

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert calls == []


@pytest.mark.unit
async def test_tick_skips_already_expired_clearance_without_decision() -> None:
    """A clearance expired under us (ClearanceCannotExpireError): no Decision written."""
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances([_item(cid, valid_until=_PAST)])
    expire_clearance = _make_raising_expire(
        ClearanceCannotExpireError(cid, ClearanceStatus.EXPIRED)
    )

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(cid)) is None


@pytest.mark.unit
async def test_tick_skips_vanished_clearance() -> None:
    """A clearance not found (state race) is a benign no-op, not a crash."""
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances([_item(cid, valid_until=_PAST)])
    expire_clearance = _make_raising_expire(ClearanceNotFoundError(cid))

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(cid)) is None


@pytest.mark.unit
async def test_tick_swallows_invalid_reason() -> None:
    """The defensive InvalidClearanceExpireReasonError arm is logged, not raised."""
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances([_item(cid, valid_until=_PAST)])
    expire_clearance = _make_raising_expire(InvalidClearanceExpireReasonError(""))

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(cid)) is None


@pytest.mark.unit
async def test_tick_swallows_unauthorized_expire() -> None:
    """An Authorize Deny (config fault) is logged, not raised; no autonomous action."""
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances([_item(cid, valid_until=_PAST)])
    expire_clearance = _make_raising_expire(UnauthorizedError("not granted ExpireClearance"))

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert await load_decision(kernel.event_store, _derive_decision_id(cid)) is None


@pytest.mark.unit
async def test_tick_drains_paginated_active_clearances() -> None:
    from cora.api._clearance_expirer import _expire_tick

    kernel = _kernel()
    await seed_clearance_expirer_agent(kernel)
    cid = uuid4()
    item = _item(cid, valid_until=_PAST)

    async def list_clearances(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage:
        if query.status != "Active":
            return ClearanceListPage(items=[], next_cursor=None)
        if query.cursor is None:
            return ClearanceListPage(items=[item], next_cursor="page2")
        return ClearanceListPage(items=[], next_cursor=None)

    expire_clearance, calls = _make_recording_expire()

    await _expire_tick(
        deps=kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    )

    assert len(calls) == 1
    assert calls[0].clearance_id == cid


@pytest.mark.unit
async def test_record_decision_is_idempotent_on_repeated_id() -> None:
    """A re-derived Decision id is a ConcurrencyError no-op, not a crash."""
    from cora.api._clearance_expirer import _record_decision

    kernel = _kernel()
    cid = uuid4()
    decision_id = _derive_decision_id(cid)
    await _record_decision(
        kernel, decision_id=decision_id, clearance_id=cid, valid_until=_PAST, now=_NOW
    )
    await _record_decision(
        kernel, decision_id=decision_id, clearance_id=cid, valid_until=_PAST, now=_NOW
    )


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    """Default settings (clearance_expirer_enabled=False): clean no-op, no task."""
    kernel = _kernel()
    list_clearances = _make_list_clearances([_item(uuid4(), valid_until=_PAST)])
    expire_clearance, calls = _make_recording_expire()

    async with clearance_expirer_lifespan(
        kernel, list_clearances=list_clearances, expire_clearance=expire_clearance
    ):
        pass

    assert calls == []


@pytest.mark.unit
async def test_lifespan_enabled_runs_the_loop_and_expires() -> None:
    """Enabled: the lifespan spawns the loop, which expires an elapsed clearance."""
    kernel = _kernel(enabled=True)
    await seed_clearance_expirer_agent(kernel)
    list_clearances = _make_list_clearances([_item(uuid4(), valid_until=_PAST)])
    expire_clearance, calls = _make_recording_expire()

    async with clearance_expirer_lifespan(
        kernel,
        list_clearances=list_clearances,
        expire_clearance=expire_clearance,
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.1)

    assert len(calls) >= 1


@pytest.mark.unit
async def test_loop_survives_a_failing_tick() -> None:
    """A tick that raises is logged and the loop keeps going; the lifespan exits cleanly."""
    kernel = _kernel(enabled=True)
    await seed_clearance_expirer_agent(kernel)
    expire_clearance, calls = _make_recording_expire()

    async def failing_list_clearances(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage:
        raise RuntimeError("list_clearances boom")

    async with clearance_expirer_lifespan(
        kernel,
        list_clearances=failing_list_clearances,
        expire_clearance=expire_clearance,
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.05)

    assert calls == []


@pytest.mark.unit
def test_clearance_expirer_tick_seconds_rejects_sub_floor() -> None:
    with pytest.raises(ValueError, match="clearance_expirer_tick_seconds"):
        Settings(clearance_expirer_tick_seconds=0.05)  # type: ignore[call-arg]


@pytest.mark.unit
def test_clearance_expirer_tick_seconds_accepts_valid() -> None:
    assert (
        Settings(clearance_expirer_tick_seconds=120.0).clearance_expirer_tick_seconds == 120.0  # type: ignore[call-arg]
    )

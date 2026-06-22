"""Tests for the ClearanceWatcher runtime (cora.api._clearance_watcher).

Covers the pure staleness rule (is_stalled) on both sides of the inclusive
boundary, plus a fakes-driven tick that exercises the full
select -> (review-step recency guard) -> flag Decision loop, the active-review
false-positive guard, the Actor.active revocation gate, multi-status drain, the
None-timestamp skip, idempotency, and the disabled no-op.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_clearance_watcher import (
    CLEARANCE_WATCHER_AGENT_ID,
    seed_clearance_watcher_agent,
)
from cora.api._clearance_watcher import (
    _derive_decision_id,
    clearance_watcher_lifespan,
    is_stalled,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.safety.aggregates.clearance import (
    Clearance,
    ClearanceStatus,
    ClearanceTitle,
    ReviewStep,
)
from cora.safety.aggregates.clearance_template import (
    ClearanceTemplateId,
    clearance_template_stream_id,
)
from cora.safety.features.get_clearance import GetClearance
from cora.safety.features.list_clearances import (
    ClearanceListPage,
    ClearanceSummaryItem,
    ListClearances,
)
from cora.shared.facility_code import FacilityCode
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC)
_OLD = _NOW - timedelta(hours=2)  # clearly stalled at the 1h window
_RECENT = _NOW - timedelta(minutes=1)  # fresh
_BOUNDARY = _NOW - timedelta(hours=1)  # exactly the 3600s window
_STALE_AFTER = 3600.0


# ---------- pure rule: is_stalled ----------


@pytest.mark.unit
def test_is_stalled_when_last_progress_old() -> None:
    assert is_stalled(_OLD, _NOW, _STALE_AFTER) is True


@pytest.mark.unit
def test_is_not_stalled_when_last_progress_recent() -> None:
    assert is_stalled(_RECENT, _NOW, _STALE_AFTER) is False


@pytest.mark.unit
def test_stalled_is_inclusive_at_boundary() -> None:
    """Elapsed == window FLAGS (inclusive >=); pins the `>`-vs-`>=` mutant."""
    assert is_stalled(_BOUNDARY, _NOW, _STALE_AFTER) is True


@pytest.mark.unit
def test_not_stalled_just_under_boundary() -> None:
    just_under = _NOW - timedelta(seconds=int(_STALE_AFTER) - 1)
    assert is_stalled(just_under, _NOW, _STALE_AFTER) is False


# ---------- tick: full loop with fakes ----------


def _kernel(*, enabled: bool = False, stale_after: float = _STALE_AFTER) -> Kernel:
    settings = Settings(  # type: ignore[call-arg]
        clearance_watcher_enabled=enabled,
        clearance_watcher_stale_after_seconds=stale_after,
    )
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _item(
    clearance_id: UUID,
    *,
    status: str,
    last_status_changed_at: datetime | None,
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
        registered_at=_OLD,
        last_status_changed_at=last_status_changed_at,
        last_status_reason=None,
        last_reviewed_by=None,
        valid_from=None,
        valid_until=None,
        next_review_due_at=None,
    )


def _make_list_clearances(items: list[ClearanceSummaryItem]):
    async def list_clearances(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage:
        matching = [i for i in items if i.status == query.status]
        return ClearanceListPage(items=matching, next_cursor=None)

    return list_clearances


def _clearance_under_review_with_step(clearance_id: UUID, decided_at: datetime) -> Clearance:
    return Clearance(
        id=clearance_id,
        template_id=ClearanceTemplateId(clearance_template_stream_id("aps", "ESAF")),
        facility_code=FacilityCode("aps"),
        title=ClearanceTitle("Pilot"),
        bindings=frozenset(),
        review_steps=(
            ReviewStep(
                step_index=0,
                role="ESH",
                decided_by=ActorId(uuid4()),
                decision="RequestedChanges",
                decided_at=decided_at,
            ),
        ),
        status=ClearanceStatus.UNDER_REVIEW,
    )


def _make_get_clearance(by_id: dict[UUID, Clearance | None]):
    async def get_clearance(
        query: GetClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Clearance | None:
        return by_id.get(query.clearance_id)

    return get_clearance


async def _no_get_clearance(
    query: GetClearance,
    *,
    principal_id: UUID,
    correlation_id: UUID,
    surface_id: UUID = NIL_SENTINEL_ID,
) -> Clearance | None:
    """get_clearance fake for paths that must not consult the aggregate."""
    raise AssertionError("get_clearance should not be called for this case")


@pytest.mark.unit
async def test_tick_flags_stale_submitted_and_records_decision() -> None:
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="Submitted", last_status_changed_at=_OLD)]
    )

    await _watch_tick(deps=kernel, list_clearances=list_clearances, get_clearance=_no_get_clearance)

    decision = await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD))
    assert decision is not None
    assert decision.context.value == "ClearanceProgress"
    assert decision.choice.value == "Flag"
    assert decision.decided_by == ActorId(CLEARANCE_WATCHER_AGENT_ID)


@pytest.mark.unit
async def test_tick_flags_stale_approved() -> None:
    """Approved-but-not-Active is a real stall the watcher surfaces."""
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="Approved", last_status_changed_at=_OLD)]
    )

    await _watch_tick(deps=kernel, list_clearances=list_clearances, get_clearance=_no_get_clearance)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_tick_skips_fresh_clearance() -> None:
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="Submitted", last_status_changed_at=_RECENT)]
    )

    await _watch_tick(deps=kernel, list_clearances=list_clearances, get_clearance=_no_get_clearance)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _RECENT)) is None


@pytest.mark.unit
async def test_tick_skips_clearance_without_status_timestamp() -> None:
    """A None last_status_changed_at cannot be evaluated: no flag, no get_clearance."""
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="UnderReview", last_status_changed_at=None)]
    )

    await _watch_tick(deps=kernel, list_clearances=list_clearances, get_clearance=_no_get_clearance)

    # No Decision under any plausible episode id (probe with _OLD).
    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_tick_does_not_flag_under_review_with_recent_step() -> None:
    """False-positive guard: an UnderReview clearance whose status ts is old but
    whose latest review step is recent is NOT flagged (active review)."""
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="UnderReview", last_status_changed_at=_OLD)]
    )
    get_clearance = _make_get_clearance({cid: _clearance_under_review_with_step(cid, _RECENT)})

    await _watch_tick(deps=kernel, list_clearances=list_clearances, get_clearance=get_clearance)

    # Not flagged on the status ts (old) nor on the recent review step.
    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None
    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _RECENT)) is None


@pytest.mark.unit
async def test_tick_flags_under_review_with_old_step() -> None:
    """An UnderReview clearance whose latest review step is also old IS flagged,
    keyed on the most recent progress (the step)."""
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    step_at = _NOW - timedelta(hours=3)  # older than status ts, still stale
    list_clearances = _make_list_clearances(
        [_item(cid, status="UnderReview", last_status_changed_at=_OLD)]
    )
    get_clearance = _make_get_clearance({cid: _clearance_under_review_with_step(cid, step_at)})

    await _watch_tick(deps=kernel, list_clearances=list_clearances, get_clearance=get_clearance)

    # last_progress_at = max(_OLD, step_at) = _OLD (status ts is the more recent).
    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_tick_watches_only_pre_active_states() -> None:
    """The watched set is exactly {Submitted, UnderReview, Approved}: a stale
    Defined / Active / Expired / Rejected clearance is NOT flagged. Pins
    `_WATCHED_STATUSES` against a mutant that widens it, exercises a multi-status
    drain in one tick, and covers the get_clearance-returns-None path for a stale
    UnderReview candidate (it flags on the status timestamp)."""
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    watched = {status: uuid4() for status in ("Submitted", "UnderReview", "Approved")}
    unwatched = {status: uuid4() for status in ("Defined", "Active", "Expired", "Rejected")}
    items = [
        _item(cid, status=status, last_status_changed_at=_OLD)
        for status, cid in (watched | unwatched).items()
    ]
    # The UnderReview candidate looks stale, so the runtime consults get_clearance;
    # returning None (no review steps) means it flags on the status timestamp.
    get_clearance = _make_get_clearance({watched["UnderReview"]: None})

    await _watch_tick(
        deps=kernel,
        list_clearances=_make_list_clearances(items),
        get_clearance=get_clearance,
    )

    for cid in watched.values():
        assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None
    for cid in unwatched.values():
        assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_tick_is_noop_when_watcher_actor_absent() -> None:
    """Revocation gate: with no seeded (active) ClearanceWatcher Actor, do nothing."""
    from cora.api._clearance_watcher import _watch_tick

    kernel = _kernel()  # NOT seeded
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="Submitted", last_status_changed_at=_OLD)]
    )

    await _watch_tick(deps=kernel, list_clearances=list_clearances, get_clearance=_no_get_clearance)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_record_decision_is_idempotent_on_repeated_episode() -> None:
    """Re-flagging the same stall episode is a ConcurrencyError no-op, not a crash."""
    from cora.api._clearance_watcher import _record_decision

    kernel = _kernel()
    cid = uuid4()
    await _record_decision(
        kernel, clearance_id=cid, status="Submitted", last_progress_at=_OLD, now=_NOW
    )
    await _record_decision(
        kernel, clearance_id=cid, status="Submitted", last_progress_at=_OLD, now=_NOW
    )
    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    """Default settings (clearance_watcher_enabled=False): clean no-op, no task."""
    kernel = _kernel()
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="Submitted", last_status_changed_at=_OLD)]
    )

    async with clearance_watcher_lifespan(
        kernel, list_clearances=list_clearances, get_clearance=_no_get_clearance
    ):
        pass

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_lifespan_enabled_runs_the_loop_and_flags() -> None:
    """Enabled: the lifespan spawns the loop, which flags a stale clearance."""
    kernel = _kernel(enabled=True)
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="Submitted", last_status_changed_at=_OLD)]
    )

    async with clearance_watcher_lifespan(
        kernel,
        list_clearances=list_clearances,
        get_clearance=_no_get_clearance,
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.1)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_loop_survives_a_failing_tick() -> None:
    """A tick that raises is logged and the loop keeps going; the lifespan exits cleanly."""
    kernel = _kernel(enabled=True)
    await seed_clearance_watcher_agent(kernel)

    async def failing_list_clearances(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage:
        raise RuntimeError("list_clearances boom")

    async with clearance_watcher_lifespan(
        kernel,
        list_clearances=failing_list_clearances,
        get_clearance=_no_get_clearance,
        interval_seconds=0.01,
    ):
        await asyncio.sleep(0.05)


@pytest.mark.unit
def test_clearance_watcher_tick_seconds_rejects_sub_floor() -> None:
    with pytest.raises(ValueError, match="clearance_watcher_tick_seconds"):
        Settings(clearance_watcher_tick_seconds=0.05)  # type: ignore[call-arg]


@pytest.mark.unit
def test_clearance_watcher_stale_after_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="clearance_watcher_stale_after_seconds"):
        Settings(clearance_watcher_stale_after_seconds=0.0)  # type: ignore[call-arg]


@pytest.mark.unit
def test_clearance_watcher_settings_accept_valid() -> None:
    settings = Settings(  # type: ignore[call-arg]
        clearance_watcher_tick_seconds=120.0,
        clearance_watcher_stale_after_seconds=86400.0,
    )
    assert settings.clearance_watcher_tick_seconds == 120.0
    assert settings.clearance_watcher_stale_after_seconds == 86400.0


@pytest.mark.unit
async def test_tick_raises_read_unauthorized_when_drain_denied() -> None:
    """A Denied ListClearances read (missing grant) surfaces as the scaffold's
    WatcherReadUnauthorizedError, not a buried generic tick failure."""
    from cora.api._clearance_watcher import _watch_tick
    from cora.api._flag_watcher import WatcherReadUnauthorizedError
    from cora.safety.errors import UnauthorizedError

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)

    async def denying_list_clearances(
        query: ListClearances,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> ClearanceListPage:
        raise UnauthorizedError("agent not granted ListClearances")

    with pytest.raises(WatcherReadUnauthorizedError) as exc:
        await _watch_tick(
            deps=kernel, list_clearances=denying_list_clearances, get_clearance=_no_get_clearance
        )
    assert exc.value.query_name == "ListClearances"


@pytest.mark.unit
async def test_tick_raises_read_unauthorized_when_get_clearance_denied() -> None:
    """A partial grant (ListClearances yes, GetClearance no) must NOT silently
    re-blind: the UnderReview fold's denied get_clearance also surfaces loudly."""
    from cora.api._clearance_watcher import _watch_tick
    from cora.api._flag_watcher import WatcherReadUnauthorizedError
    from cora.safety.aggregates.clearance import Clearance
    from cora.safety.errors import UnauthorizedError

    kernel = _kernel()
    await seed_clearance_watcher_agent(kernel)
    cid = uuid4()
    list_clearances = _make_list_clearances(
        [_item(cid, status="UnderReview", last_status_changed_at=_OLD)]
    )

    async def denying_get_clearance(
        query: GetClearance,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> Clearance | None:
        raise UnauthorizedError("agent not granted GetClearance")

    with pytest.raises(WatcherReadUnauthorizedError) as exc:
        await _watch_tick(
            deps=kernel, list_clearances=list_clearances, get_clearance=denying_get_clearance
        )
    assert exc.value.query_name == "GetClearance"

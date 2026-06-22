"""Tests for the CalibrationWatcher runtime (cora.api._calibration_watcher).

Covers the pure staleness rule (is_stalled) on both sides of the inclusive
boundary, plus a fakes-driven tick that exercises the drain -> flag Decision
loop, the Provisional-only / defensive-status guard, the Actor.active revocation
gate, idempotency, and the disabled no-op.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_calibration_watcher import (
    CALIBRATION_WATCHER_AGENT_ID,
    seed_calibration_watcher_agent,
)
from cora.api._calibration_watcher import (
    _derive_decision_id,
    calibration_watcher_lifespan,
    is_stalled,
)
from cora.calibration.features.list_calibrations import (
    CalibrationListPage,
    CalibrationSummaryItem,
    ListCalibrations,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.shared.identity import ActorId

_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
_OLD = _NOW - timedelta(days=60)  # clearly stale at a 30-day window
_RECENT = _NOW - timedelta(minutes=1)  # fresh
_STALE_AFTER = 2592000.0  # 30 days
_BOUNDARY = _NOW - timedelta(seconds=int(_STALE_AFTER))


# ---------- pure rule: is_stalled ----------


@pytest.mark.unit
def test_is_stalled_when_revision_old() -> None:
    assert is_stalled(_OLD, _NOW, _STALE_AFTER) is True


@pytest.mark.unit
def test_is_not_stalled_when_revision_recent() -> None:
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
        calibration_watcher_enabled=enabled,
        calibration_watcher_stale_after_seconds=stale_after,
    )
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _item(
    calibration_id: UUID,
    *,
    status: str = "Provisional",
    last_revised_at: datetime,
) -> CalibrationSummaryItem:
    return CalibrationSummaryItem(
        calibration_id=calibration_id,
        target_id=uuid4(),
        quantity="rotation_center",
        operating_point={},
        description=None,
        defined_at=_OLD,
        last_revised_at=last_revised_at,
        defined_by=ActorId(uuid4()),
        revision_count=1,
        latest_revision_status=status,
        latest_revision_source_kind="measured",
    )


def _make_list_calibrations(items: list[CalibrationSummaryItem], *, honor_filter: bool = True):
    async def list_calibrations(
        query: ListCalibrations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CalibrationListPage:
        wanted = query.latest_revision_statuses
        if honor_filter and wanted:
            matching = [i for i in items if i.latest_revision_status in wanted]
        else:
            matching = list(items)
        return CalibrationListPage(items=matching, next_cursor=None)

    return list_calibrations


@pytest.mark.unit
async def test_tick_flags_stale_provisional_and_records_decision() -> None:
    from cora.api._calibration_watcher import _watch_tick

    kernel = _kernel()
    await seed_calibration_watcher_agent(kernel)
    cid = uuid4()
    list_calibrations = _make_list_calibrations([_item(cid, last_revised_at=_OLD)])

    await _watch_tick(deps=kernel, list_calibrations=list_calibrations)

    decision = await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD))
    assert decision is not None
    assert decision.context.value == "CalibrationVerification"
    assert decision.choice.value == "Stale"
    assert decision.decided_by == ActorId(CALIBRATION_WATCHER_AGENT_ID)


@pytest.mark.unit
async def test_tick_skips_fresh_provisional() -> None:
    from cora.api._calibration_watcher import _watch_tick

    kernel = _kernel()
    await seed_calibration_watcher_agent(kernel)
    cid = uuid4()
    list_calibrations = _make_list_calibrations([_item(cid, last_revised_at=_RECENT)])

    await _watch_tick(deps=kernel, list_calibrations=list_calibrations)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _RECENT)) is None


@pytest.mark.unit
async def test_tick_skips_verified_calibration_even_if_unfiltered() -> None:
    """Defensive guard: a Verified (not Provisional) calibration is never flagged,
    even if the drain returned it. Pins the status check against a filter widening."""
    from cora.api._calibration_watcher import _watch_tick

    kernel = _kernel()
    await seed_calibration_watcher_agent(kernel)
    cid = uuid4()
    list_calibrations = _make_list_calibrations(
        [_item(cid, status="Verified", last_revised_at=_OLD)], honor_filter=False
    )

    await _watch_tick(deps=kernel, list_calibrations=list_calibrations)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_record_decision_is_idempotent_on_repeated_episode() -> None:
    """Re-flagging the same stale revision is a ConcurrencyError no-op, not a crash."""
    from cora.api._calibration_watcher import _record_decision

    kernel = _kernel()
    cid = uuid4()
    await _record_decision(
        kernel, calibration_id=cid, quantity="rotation_center", last_revised_at=_OLD, now=_NOW
    )
    await _record_decision(
        kernel, calibration_id=cid, quantity="rotation_center", last_revised_at=_OLD, now=_NOW
    )
    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_tick_is_noop_when_watcher_actor_absent() -> None:
    """Revocation gate: with no seeded (active) CalibrationWatcher Actor, do nothing."""
    from cora.api._calibration_watcher import _watch_tick

    kernel = _kernel()  # NOT seeded
    cid = uuid4()
    list_calibrations = _make_list_calibrations([_item(cid, last_revised_at=_OLD)])

    await _watch_tick(deps=kernel, list_calibrations=list_calibrations)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    """Default settings (calibration_watcher_enabled=False): clean no-op, no task."""
    kernel = _kernel()
    cid = uuid4()
    list_calibrations = _make_list_calibrations([_item(cid, last_revised_at=_OLD)])

    async with calibration_watcher_lifespan(kernel, list_calibrations=list_calibrations):
        pass

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_lifespan_enabled_runs_the_loop_and_flags() -> None:
    """Enabled: the lifespan spawns the loop, which flags a stale calibration."""
    kernel = _kernel(enabled=True)
    await seed_calibration_watcher_agent(kernel)
    cid = uuid4()
    list_calibrations = _make_list_calibrations([_item(cid, last_revised_at=_OLD)])

    async with calibration_watcher_lifespan(
        kernel, list_calibrations=list_calibrations, interval_seconds=0.01
    ):
        await asyncio.sleep(0.1)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_loop_survives_a_failing_tick() -> None:
    """A tick that raises is logged and the loop keeps going; lifespan exits cleanly."""
    kernel = _kernel(enabled=True)
    await seed_calibration_watcher_agent(kernel)

    async def failing_list_calibrations(
        query: ListCalibrations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CalibrationListPage:
        raise RuntimeError("list_calibrations boom")

    async with calibration_watcher_lifespan(
        kernel, list_calibrations=failing_list_calibrations, interval_seconds=0.01
    ):
        await asyncio.sleep(0.05)


@pytest.mark.unit
def test_calibration_watcher_tick_seconds_rejects_sub_floor() -> None:
    with pytest.raises(ValueError, match="calibration_watcher_tick_seconds"):
        Settings(calibration_watcher_tick_seconds=0.05)  # type: ignore[call-arg]


@pytest.mark.unit
def test_calibration_watcher_stale_after_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="calibration_watcher_stale_after_seconds"):
        Settings(calibration_watcher_stale_after_seconds=0.0)  # type: ignore[call-arg]


@pytest.mark.unit
def test_calibration_watcher_settings_accept_valid() -> None:
    settings = Settings(  # type: ignore[call-arg]
        calibration_watcher_tick_seconds=120.0,
        calibration_watcher_stale_after_seconds=86400.0,
    )
    assert settings.calibration_watcher_tick_seconds == 120.0
    assert settings.calibration_watcher_stale_after_seconds == 86400.0


@pytest.mark.unit
async def test_tick_raises_read_unauthorized_when_drain_denied() -> None:
    """A Denied ListCalibrations read (missing grant) surfaces as the scaffold's
    WatcherReadUnauthorizedError, not a buried generic tick failure."""
    from cora.api._calibration_watcher import _watch_tick
    from cora.api._flag_watcher import WatcherReadUnauthorizedError
    from cora.calibration.errors import UnauthorizedError

    kernel = _kernel()
    await seed_calibration_watcher_agent(kernel)

    async def denying_list_calibrations(
        query: ListCalibrations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CalibrationListPage:
        raise UnauthorizedError("agent not granted ListCalibrations")

    with pytest.raises(WatcherReadUnauthorizedError) as exc:
        await _watch_tick(deps=kernel, list_calibrations=denying_list_calibrations)
    assert exc.value.query_name == "ListCalibrations"

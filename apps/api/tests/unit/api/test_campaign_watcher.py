"""Tests for the CampaignWatcher runtime (cora.api._campaign_watcher).

Covers the pure staleness rule (is_stalled, from the shared scaffold) on both
sides of the inclusive boundary, plus a fakes-driven tick that exercises the
drain -> flag Decision loop, the Held-only / defensive-status guard, the
cannot-tell defer, the paginated drain, the Actor.active revocation + deactivation
gates, idempotency, and the disabled / failing-tick lifespan behavior.
"""

# white-box test of the runtime internals (private functions / constants)
# pyright: reportPrivateUsage=false

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from cora.agent.seed_campaign_watcher import (
    CAMPAIGN_WATCHER_AGENT_ID,
    seed_campaign_watcher_agent,
)
from cora.api._campaign_watcher import (
    _derive_decision_id,
    campaign_watcher_lifespan,
    is_stalled,
)
from cora.campaign.features.list_campaigns import (
    CampaignListPage,
    CampaignSummaryItem,
    ListCampaigns,
)
from cora.decision.aggregates.decision import load_decision
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.config import Settings
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, UUIDv7Generator
from cora.infrastructure.routing import NIL_SENTINEL_ID

_NOW = datetime(2026, 6, 22, 12, 0, 0, tzinfo=UTC)
_STALE_AFTER = 604800.0  # 7 days
_OLD = _NOW - timedelta(days=14)  # clearly stale at a 7-day window
_RECENT = _NOW - timedelta(hours=1)  # fresh
_BOUNDARY = _NOW - timedelta(seconds=int(_STALE_AFTER))


# ---------- pure rule: is_stalled ----------


@pytest.mark.unit
def test_is_stalled_when_held_old() -> None:
    assert is_stalled(_OLD, _NOW, _STALE_AFTER) is True


@pytest.mark.unit
def test_is_not_stalled_when_held_recent() -> None:
    assert is_stalled(_RECENT, _NOW, _STALE_AFTER) is False


@pytest.mark.unit
def test_stalled_is_inclusive_at_boundary() -> None:
    """Elapsed == window FLAGS (inclusive >=); pins the `>`-vs-`>=` mutant."""
    assert is_stalled(_BOUNDARY, _NOW, _STALE_AFTER) is True


# ---------- tick: full loop with fakes ----------


def _kernel(*, enabled: bool = False, stale_after: float = _STALE_AFTER) -> Kernel:
    settings = Settings(  # type: ignore[call-arg]
        campaign_watcher_enabled=enabled,
        campaign_watcher_stale_after_seconds=stale_after,
    )
    return make_inmemory_kernel(
        settings=settings,
        clock=FakeClock(_NOW),
        id_generator=UUIDv7Generator(),
        authz=AllowAllAuthorize(),
    )


def _item(
    campaign_id: UUID,
    *,
    status: str = "Held",
    last_status_changed_at: datetime | None,
) -> CampaignSummaryItem:
    return CampaignSummaryItem(
        campaign_id=campaign_id,
        name="winter-tomo-series",
        intent="Series",
        status=status,
        lead_actor_id=uuid4(),
        subject_id=None,
        description=None,
        tags=[],
        external_id=None,
        run_count=0,
        registered_at=_OLD,
        started_at=_OLD,
        last_status_changed_at=last_status_changed_at,
        last_status_reason="paused for beam study",
    )


def _make_list_campaigns(items: list[CampaignSummaryItem], *, honor_filter: bool = True):
    async def list_campaigns(
        query: ListCampaigns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CampaignListPage:
        wanted = query.statuses
        if honor_filter and wanted:
            matching = [i for i in items if i.status in wanted]
        else:
            matching = list(items)
        return CampaignListPage(items=matching, next_cursor=None)

    return list_campaigns


async def _campaign_progress_decision_count(kernel: Kernel) -> int:
    """Count CampaignProgress Decisions written to the event store."""
    store = kernel.event_store
    assert isinstance(store, InMemoryEventStore)
    count = 0
    for stream_type, stream_id in store._streams:
        if stream_type != "Decision":
            continue
        decision = await load_decision(store, stream_id)
        if decision is not None and decision.context.value == "CampaignProgress":
            count += 1
    return count


@pytest.mark.unit
async def test_tick_flags_stuck_held_and_records_decision() -> None:
    from cora.api._campaign_watcher import _watch_tick

    kernel = _kernel()
    await seed_campaign_watcher_agent(kernel)
    cid = uuid4()
    list_campaigns = _make_list_campaigns([_item(cid, last_status_changed_at=_OLD)])

    await _watch_tick(deps=kernel, list_campaigns=list_campaigns)

    decision = await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD))
    assert decision is not None
    assert decision.context.value == "CampaignProgress"
    assert decision.choice.value == "Stuck"


@pytest.mark.unit
async def test_tick_skips_fresh_held() -> None:
    from cora.api._campaign_watcher import _watch_tick

    kernel = _kernel()
    await seed_campaign_watcher_agent(kernel)
    cid = uuid4()
    list_campaigns = _make_list_campaigns([_item(cid, last_status_changed_at=_RECENT)])

    await _watch_tick(deps=kernel, list_campaigns=list_campaigns)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _RECENT)) is None


@pytest.mark.unit
async def test_tick_does_not_flag_when_status_timestamp_missing() -> None:
    """cannot-tell -> defer: a Held row with no last_status_changed_at is skipped."""
    from cora.api._campaign_watcher import _watch_tick

    kernel = _kernel()
    await seed_campaign_watcher_agent(kernel)
    cid = uuid4()
    list_campaigns = _make_list_campaigns([_item(cid, last_status_changed_at=None)])

    await _watch_tick(deps=kernel, list_campaigns=list_campaigns)

    assert await _campaign_progress_decision_count(kernel) == 0


@pytest.mark.unit
async def test_tick_skips_non_held_status_even_if_unfiltered() -> None:
    """Defensive guard: a non-Held campaign is never flagged, even if the drain
    returned it. Pins the status check against a filter widening."""
    from cora.api._campaign_watcher import _watch_tick

    kernel = _kernel()
    await seed_campaign_watcher_agent(kernel)
    cid = uuid4()
    list_campaigns = _make_list_campaigns(
        [_item(cid, status="Active", last_status_changed_at=_OLD)], honor_filter=False
    )

    await _watch_tick(deps=kernel, list_campaigns=list_campaigns)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_tick_drains_paginated_campaigns() -> None:
    """The drain follows next_cursor across pages, so a stuck campaign on a later
    page is still flagged (pins the cursor-advance against a mutant)."""
    from cora.api._campaign_watcher import _watch_tick

    kernel = _kernel()
    await seed_campaign_watcher_agent(kernel)
    page1_cid, page2_cid = uuid4(), uuid4()

    async def list_campaigns(
        query: ListCampaigns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CampaignListPage:
        if query.cursor is None:
            return CampaignListPage(
                items=[_item(page1_cid, last_status_changed_at=_OLD)], next_cursor="page2"
            )
        return CampaignListPage(
            items=[_item(page2_cid, last_status_changed_at=_OLD)], next_cursor=None
        )

    await _watch_tick(deps=kernel, list_campaigns=list_campaigns)

    assert await load_decision(kernel.event_store, _derive_decision_id(page2_cid, _OLD)) is not None


@pytest.mark.unit
async def test_record_decision_is_idempotent_on_repeated_episode() -> None:
    """Re-flagging the same stuck episode is a ConcurrencyError no-op, not a crash."""
    from cora.api._campaign_watcher import _record_decision

    kernel = _kernel()
    cid = uuid4()
    await _record_decision(kernel, campaign_id=cid, name="c", last_status_changed_at=_OLD, now=_NOW)
    await _record_decision(kernel, campaign_id=cid, name="c", last_status_changed_at=_OLD, now=_NOW)
    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_tick_is_noop_when_watcher_actor_absent() -> None:
    """Revocation gate: with no seeded (active) CampaignWatcher Actor, do nothing."""
    from cora.api._campaign_watcher import _watch_tick

    kernel = _kernel()  # NOT seeded
    cid = uuid4()
    list_campaigns = _make_list_campaigns([_item(cid, last_status_changed_at=_OLD)])

    await _watch_tick(deps=kernel, list_campaigns=list_campaigns)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_tick_is_noop_when_watcher_actor_deactivated() -> None:
    """Kill switch: an operator deactivating the agent Actor stands the watcher
    down even while seeded. Pins the `not actor.active` disjunct of the gate."""
    from cora.access.features import deactivate_actor
    from cora.access.features.deactivate_actor import DeactivateActor
    from cora.api._campaign_watcher import _watch_tick

    kernel = _kernel()
    await seed_campaign_watcher_agent(kernel)
    await deactivate_actor.bind(kernel)(
        DeactivateActor(actor_id=CAMPAIGN_WATCHER_AGENT_ID),
        principal_id=CAMPAIGN_WATCHER_AGENT_ID,
        correlation_id=uuid4(),
    )
    cid = uuid4()
    list_campaigns = _make_list_campaigns([_item(cid, last_status_changed_at=_OLD)])

    await _watch_tick(deps=kernel, list_campaigns=list_campaigns)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_lifespan_is_noop_when_disabled() -> None:
    """Default settings (campaign_watcher_enabled=False): clean no-op, no task."""
    kernel = _kernel()
    cid = uuid4()
    list_campaigns = _make_list_campaigns([_item(cid, last_status_changed_at=_OLD)])

    async with campaign_watcher_lifespan(kernel, list_campaigns=list_campaigns):
        pass

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is None


@pytest.mark.unit
async def test_lifespan_enabled_runs_the_loop_and_flags() -> None:
    """Enabled: the lifespan spawns the loop, which flags a stuck campaign."""
    kernel = _kernel(enabled=True)
    await seed_campaign_watcher_agent(kernel)
    cid = uuid4()
    list_campaigns = _make_list_campaigns([_item(cid, last_status_changed_at=_OLD)])

    async with campaign_watcher_lifespan(
        kernel, list_campaigns=list_campaigns, interval_seconds=0.01
    ):
        await asyncio.sleep(0.1)

    assert await load_decision(kernel.event_store, _derive_decision_id(cid, _OLD)) is not None


@pytest.mark.unit
async def test_loop_survives_a_failing_tick() -> None:
    """A tick that raises is logged and the loop keeps going; lifespan exits cleanly."""
    kernel = _kernel(enabled=True)
    await seed_campaign_watcher_agent(kernel)

    async def failing_list_campaigns(
        query: ListCampaigns,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> CampaignListPage:
        raise RuntimeError("list_campaigns boom")

    async with campaign_watcher_lifespan(
        kernel, list_campaigns=failing_list_campaigns, interval_seconds=0.01
    ):
        await asyncio.sleep(0.05)


@pytest.mark.unit
def test_campaign_watcher_tick_seconds_rejects_sub_floor() -> None:
    with pytest.raises(ValueError, match="campaign_watcher_tick_seconds"):
        Settings(campaign_watcher_tick_seconds=0.05)  # type: ignore[call-arg]


@pytest.mark.unit
def test_campaign_watcher_stale_after_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="campaign_watcher_stale_after_seconds"):
        Settings(campaign_watcher_stale_after_seconds=0.0)  # type: ignore[call-arg]


@pytest.mark.unit
def test_campaign_watcher_settings_accept_valid() -> None:
    settings = Settings(  # type: ignore[call-arg]
        campaign_watcher_tick_seconds=120.0,
        campaign_watcher_stale_after_seconds=86400.0,
    )
    assert settings.campaign_watcher_tick_seconds == 120.0
    assert settings.campaign_watcher_stale_after_seconds == 86400.0

"""End-to-end: `list_campaigns` handler + CampaignSummaryProjection
against real Postgres.

Pins:
  - CampaignRegistered -> INSERT (status='Planned',
                                  last_status_changed_at=NULL,
                                  started_at=NULL)
  - CampaignStarted    -> UPDATE status='Active' + started_at
  - CampaignHeld       -> UPDATE status='Held' + last_status_reason
                                  + last_status_changed_at
  - CampaignResumed    -> UPDATE status='Active'
                                  + last_status_changed_at
                                  (last_status_reason preserved;
                                   started_at preserved)
  - CampaignClosed     -> UPDATE status='Closed'
  - CampaignAbandoned  -> UPDATE status='Abandoned'
                                  + last_status_reason
  - tags TEXT[] round-trip + GIN-index-backed filter
  - status default (OPEN set) vs status='all' vs exact value
  - intent / lead_actor_id / subject_id / tag filter combinations
  - cursor pagination across multiple campaigns
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign._projections import register_campaign_projections
from cora.campaign.aggregates.campaign import CampaignIntent
from cora.campaign.features import (
    abandon_campaign,
    close_campaign,
    hold_campaign,
    list_campaigns,
    register_campaign,
    resume_campaign,
    start_campaign,
)
from cora.campaign.features.abandon_campaign import AbandonCampaign
from cora.campaign.features.close_campaign import CloseCampaign
from cora.campaign.features.hold_campaign import HoldCampaign
from cora.campaign.features.list_campaigns import ListCampaigns
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.resume_campaign import ResumeCampaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 17, 14, 0, 0, tzinfo=UTC)
_EVEN_LATER = datetime(2026, 5, 17, 16, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_LEAD_ACTOR_ID = UUID("01900000-0000-7000-8000-00000000c001")


def _build_deps(pool: asyncpg.Pool, ids: list[UUID], now: datetime = _NOW) -> Kernel:
    return build_postgres_deps(pool, now=now, ids=ids)


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_campaign_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


def _register_command(
    *,
    name: str = "operando battery week of 2026-05-17",
    intent: CampaignIntent = CampaignIntent.SERIES,
    lead_actor_id: UUID = _LEAD_ACTOR_ID,
    subject_id: UUID | None = None,
    description: str | None = None,
    tags: frozenset[str] = frozenset(),
) -> RegisterCampaign:
    return RegisterCampaign(
        name=name,
        intent=intent,
        lead_actor_id=lead_actor_id,
        subject_id=subject_id,
        description=description,
        tags=tags,
    )


@pytest.mark.integration
async def test_register_inserts_planned_with_null_audit_columns(db_pool: asyncpg.Pool) -> None:
    """CampaignRegistered -> row in 'Planned' with started_at +
    last_status_changed_at + last_status_reason all NULL."""
    campaign_id = uuid4()
    deps = _build_deps(db_pool, [campaign_id, uuid4()])
    await register_campaign.bind(deps)(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT name, intent, status, lead_actor_id, subject_id, "
            "description, tags, external_id, run_count, registered_at, "
            "started_at, last_status_changed_at, last_status_reason "
            "FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["name"] == "operando battery week of 2026-05-17"
    assert row["intent"] == "Series"
    assert row["status"] == "Planned"
    assert row["lead_actor_id"] == _LEAD_ACTOR_ID
    assert row["subject_id"] is None
    assert row["description"] is None
    assert list(row["tags"]) == []
    assert row["external_id"] is None
    assert row["run_count"] == 0
    assert row["registered_at"] == _NOW
    assert row["started_at"] is None
    assert row["last_status_changed_at"] is None
    assert row["last_status_reason"] is None


@pytest.mark.integration
async def test_start_flips_status_active_and_sets_started_at(db_pool: asyncpg.Pool) -> None:
    """Register -> start -> status Active + started_at + last_status_changed_at."""
    campaign_id = uuid4()
    deps = _build_deps(db_pool, [campaign_id, uuid4()])
    await register_campaign.bind(deps)(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    later_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await start_campaign.bind(later_deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, started_at, last_status_changed_at, last_status_reason "
            "FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["status"] == "Active"
    assert row["started_at"] == _LATER
    assert row["last_status_changed_at"] == _LATER
    assert row["last_status_reason"] is None


@pytest.mark.integration
async def test_hold_sets_status_held_with_reason_and_audit_ts(db_pool: asyncpg.Pool) -> None:
    """Register -> start -> hold -> status Held + last_status_reason."""
    campaign_id = uuid4()
    deps = _build_deps(db_pool, [campaign_id, uuid4()])
    await register_campaign.bind(deps)(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    start_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await start_campaign.bind(start_deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    hold_deps = _build_deps(db_pool, [uuid4()], now=_EVEN_LATER)
    await hold_campaign.bind(hold_deps)(
        HoldCampaign(campaign_id=campaign_id, reason="beam dump unscheduled outage"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, started_at, last_status_changed_at, last_status_reason "
            "FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["status"] == "Held"
    # started_at is preserved (the original Start timestamp)
    assert row["started_at"] == _LATER
    assert row["last_status_changed_at"] == _EVEN_LATER
    assert row["last_status_reason"] == "beam dump unscheduled outage"


@pytest.mark.integration
async def test_resume_preserves_reason_and_started_at(db_pool: asyncpg.Pool) -> None:
    """Register -> start -> hold(reason X) -> resume -> status Active;
    last_status_reason preserved (audit value); started_at preserved."""
    campaign_id = uuid4()
    deps = _build_deps(db_pool, [campaign_id, uuid4()])
    await register_campaign.bind(deps)(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    start_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await start_campaign.bind(start_deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    hold_deps = _build_deps(db_pool, [uuid4()], now=_EVEN_LATER)
    await hold_campaign.bind(hold_deps)(
        HoldCampaign(campaign_id=campaign_id, reason="beam dump"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    even_later_2 = datetime(2026, 5, 17, 18, 0, 0, tzinfo=UTC)
    resume_deps = _build_deps(db_pool, [uuid4()], now=even_later_2)
    await resume_campaign.bind(resume_deps)(
        ResumeCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, started_at, last_status_changed_at, last_status_reason "
            "FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["status"] == "Active"
    assert row["started_at"] == _LATER  # PRESERVED across hold + resume
    assert row["last_status_changed_at"] == even_later_2
    assert row["last_status_reason"] == "beam dump"  # PRESERVED across resume


@pytest.mark.integration
async def test_close_flips_status_closed(db_pool: asyncpg.Pool) -> None:
    """Register -> start -> close -> status Closed."""
    campaign_id = uuid4()
    deps = _build_deps(db_pool, [campaign_id, uuid4()])
    await register_campaign.bind(deps)(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    start_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await start_campaign.bind(start_deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    close_deps = _build_deps(db_pool, [uuid4()], now=_EVEN_LATER)
    await close_campaign.bind(close_deps)(
        CloseCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, started_at, last_status_changed_at "
            "FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["status"] == "Closed"
    assert row["started_at"] == _LATER
    assert row["last_status_changed_at"] == _EVEN_LATER


@pytest.mark.integration
async def test_abandon_from_planned_flips_status_abandoned_with_reason(
    db_pool: asyncpg.Pool,
) -> None:
    """Register -> abandon (from Planned, never started) -> status Abandoned;
    started_at stays NULL; last_status_reason set."""
    campaign_id = uuid4()
    deps = _build_deps(db_pool, [campaign_id, uuid4()])
    await register_campaign.bind(deps)(
        _register_command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    abandon_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await abandon_campaign.bind(abandon_deps)(
        AbandonCampaign(
            campaign_id=campaign_id,
            reason="sample shipping delayed; no longer feasible",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT status, started_at, last_status_changed_at, last_status_reason "
            "FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["status"] == "Abandoned"
    assert row["started_at"] is None  # never started
    assert row["last_status_changed_at"] == _LATER
    assert row["last_status_reason"] == "sample shipping delayed; no longer feasible"


@pytest.mark.integration
async def test_list_returns_only_open_by_default(db_pool: asyncpg.Pool) -> None:
    """Default `status` filter is OPEN set; Closed + Abandoned are hidden."""
    # 3 campaigns: planned (open), closed (terminal), abandoned (terminal).
    planned_id = uuid4()
    closed_id = uuid4()
    abandoned_id = uuid4()

    for cid in (planned_id, closed_id, abandoned_id):
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_campaign.bind(deps)(
            _register_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Bring closed_id to Closed via Active.
    start_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await start_campaign.bind(start_deps)(
        StartCampaign(campaign_id=closed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    close_deps = _build_deps(db_pool, [uuid4()], now=_EVEN_LATER)
    await close_campaign.bind(close_deps)(
        CloseCampaign(campaign_id=closed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    abandon_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await abandon_campaign.bind(abandon_deps)(
        AbandonCampaign(campaign_id=abandoned_id, reason="cancelled"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # boundary now, not in the handler. To exercise the canonical shape
    # this test pins the same operator-facing behavior by passing the
    # OPEN set explicitly.
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(statuses=["Planned", "Active", "Held"]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {item.campaign_id for item in page.items}
    assert planned_id in returned
    assert closed_id not in returned
    assert abandoned_id not in returned


@pytest.mark.integration
async def test_list_status_all_returns_every_campaign(db_pool: asyncpg.Pool) -> None:
    """Passing `statuses=None` (the canonical 'no status filter') returns
    every row. Route-layer translates user-facing `?status=all` to this
    None per the cleanup convention."""
    planned_id = uuid4()
    abandoned_id = uuid4()
    for cid in (planned_id, abandoned_id):
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_campaign.bind(deps)(
            _register_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    abandon_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await abandon_campaign.bind(abandon_deps)(
        AbandonCampaign(campaign_id=abandoned_id, reason="cancelled"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(statuses=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {item.campaign_id for item in page.items}
    assert planned_id in returned
    assert abandoned_id in returned


@pytest.mark.integration
async def test_list_status_exact_value_filters_to_that_status(db_pool: asyncpg.Pool) -> None:
    """`statuses=['Closed']` returns only Closed campaigns. This is what
    the route emits for the user-facing `?status=Closed`."""
    planned_id = uuid4()
    closed_id = uuid4()
    for cid in (planned_id, closed_id):
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_campaign.bind(deps)(
            _register_command(),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    start_deps = _build_deps(db_pool, [uuid4()], now=_LATER)
    await start_campaign.bind(start_deps)(
        StartCampaign(campaign_id=closed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    close_deps = _build_deps(db_pool, [uuid4()], now=_EVEN_LATER)
    await close_campaign.bind(close_deps)(
        CloseCampaign(campaign_id=closed_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(statuses=["Closed"]),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {item.campaign_id for item in page.items}
    assert returned == {closed_id}


@pytest.mark.integration
async def test_list_filters_by_intent_lead_actor_subject_and_tag(
    db_pool: asyncpg.Pool,
) -> None:
    """Per-column filters all narrow correctly."""
    lead_a = uuid4()
    lead_b = uuid4()
    subject_x = uuid4()

    in_situ_a_id = uuid4()
    operando_a_id = uuid4()
    operando_b_id = uuid4()
    sweep_with_subject_id = uuid4()

    seeded: list[tuple[UUID, CampaignIntent, UUID, UUID | None, frozenset[str]]] = [
        (in_situ_a_id, CampaignIntent.COORDINATION, lead_a, None, frozenset({"alpha"})),
        (
            operando_a_id,
            CampaignIntent.SERIES,
            lead_a,
            None,
            frozenset({"beta", "hexapod"}),
        ),
        (operando_b_id, CampaignIntent.SERIES, lead_b, None, frozenset({"gamma"})),
        (
            sweep_with_subject_id,
            CampaignIntent.SWEEP,
            lead_a,
            subject_x,
            frozenset(),
        ),
    ]
    for cid, intent, lead, subj, tags in seeded:
        deps = _build_deps(db_pool, [cid, uuid4()])
        await register_campaign.bind(deps)(
            _register_command(intent=intent, lead_actor_id=lead, subject_id=subj, tags=tags),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])

    # intent=Series -> 2 rows.
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(intent="Series"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {it.campaign_id for it in page.items}
    assert returned == {operando_a_id, operando_b_id}

    # lead_actor_id=lead_a -> 3 rows (in_situ_a, operando_a, sweep).
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(lead_actor_id=lead_a),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {it.campaign_id for it in page.items}
    assert returned == {in_situ_a_id, operando_a_id, sweep_with_subject_id}

    # subject_id=subject_x -> 1 row.
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(subject_id=subject_x),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {it.campaign_id for it in page.items}
    assert returned == {sweep_with_subject_id}

    # tag=hexapod -> 1 row via GIN index.
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(tag="hexapod"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    returned = {it.campaign_id for it in page.items}
    assert returned == {operando_a_id}


@pytest.mark.integration
async def test_list_tags_round_trip_preserves_array(db_pool: asyncpg.Pool) -> None:
    """Tags TEXT[] survives the projection round-trip; payload sorts the values."""
    campaign_id = uuid4()
    deps = _build_deps(db_pool, [campaign_id, uuid4()])
    await register_campaign.bind(deps)(
        _register_command(tags=frozenset({"zeta", "alpha", "mu"})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    page = await list_campaigns.bind(list_deps)(
        ListCampaigns(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert len(page.items) == 1
    # Payload tags are sorted at to_payload; projection stores as-is.
    assert sorted(page.items[0].tags) == ["alpha", "mu", "zeta"]


@pytest.mark.integration
async def test_list_cursor_pagination_across_many_campaigns(db_pool: asyncpg.Pool) -> None:
    """Page-of-10 across 25 campaigns -> first page returns 10 + cursor;
    subsequent pages drain the remainder."""
    for i in range(25):
        deps = _build_deps(db_pool, [uuid4(), uuid4()])
        await register_campaign.bind(deps)(
            _register_command(name=f"campaign {i:02d}"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    await _drain(db_pool)

    list_deps = _build_deps(db_pool, [])
    seen: set[UUID] = set()
    cursor: str | None = None
    pages_fetched = 0
    while True:
        page = await list_campaigns.bind(list_deps)(
            ListCampaigns(limit=10, cursor=cursor),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
        pages_fetched += 1
        seen.update(item.campaign_id for item in page.items)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor
        assert pages_fetched <= 5, "pagination should converge within 5 pages of 10"

    assert len(seen) == 25
    assert pages_fetched >= 3  # 10 + 10 + 5 ish

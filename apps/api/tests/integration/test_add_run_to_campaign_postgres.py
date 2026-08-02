"""End-to-end PG integration test: `add_run_to_campaign` two-stream atomic write.

Pins the cross-aggregate, multi-stream atomic-write contract under
real Postgres:

  1. Happy-path round-trip: Campaign gains run_id in its run_ids;
     Run gains campaign_id on its state. Both stream version cursors
     advance in a single transaction (shared xid8).
  2. Projection denorm: proj_campaign_summary.run_count is
     bumped after the worker drains.

Seeds Run state directly via event-store appends to avoid pulling
the full upstream Plan / Practice / Method / Asset / Subject chain
into this test (the Run aggregate's membership invariants don't
depend on that chain; the start_run upstream chain has its own
integration test at test_start_run_handler_postgres.py).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.campaign._projections import register_campaign_projections
from cora.campaign.aggregates.campaign import (
    CampaignIntent,
)
from cora.campaign.aggregates.campaign import (
    fold as campaign_fold,
)
from cora.campaign.aggregates.campaign import (
    from_stored as campaign_from_stored,
)
from cora.campaign.features import (
    abandon_campaign,
    add_run_to_campaign,
    close_campaign,
    hold_campaign,
    register_campaign,
    remove_run_from_campaign,
    start_campaign,
)
from cora.campaign.features.abandon_campaign import AbandonCampaign
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
from cora.campaign.features.close_campaign import CloseCampaign
from cora.campaign.features.hold_campaign import HoldCampaign
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.remove_run_from_campaign import RemoveRunFromCampaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.run.aggregates.run import (
    event_type_name as run_event_type_name,
)
from cora.run.aggregates.run import (
    fold as run_fold,
)
from cora.run.aggregates.run import (
    from_stored as run_from_stored,
)
from cora.run.aggregates.run import (
    to_payload as run_to_payload,
)
from cora.run.aggregates.run.events import RunStarted
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_run_via_event_store(
    deps, run_id: UUID, *, event_id: UUID, principal_id: UUID = _PRINCIPAL_ID
) -> None:
    """Append a RunStarted event directly to the Run stream."""
    event = RunStarted(
        run_id=run_id,
        name="member-run",
        plan_id=uuid4(),
        subject_id=None,
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Run",
        stream_id=run_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=run_event_type_name(event),
                payload=run_to_payload(event),
                occurred_at=event.occurred_at,
                event_id=event_id,
                command_name="seed",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=principal_id,
            )
        ],
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_campaign_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_add_run_to_campaign_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    """Happy-path: Run + Campaign exist standalone; add_run_to_campaign
    writes CampaignRunAdded on Campaign + RunAddedToCampaign on Run
    via append_streams; both streams reflect the membership."""
    campaign_id = uuid4()
    register_event_id = uuid4()
    start_event_id = uuid4()
    run_id = uuid4()
    add_campaign_event_id = uuid4()
    add_run_event_id = uuid4()
    lead = uuid4()

    # IDs consumed in order by the kernel's FixedIdGenerator:
    #   register_campaign: campaign_id + register_event_id (2)
    #   start_campaign:    start_event_id (1)
    #   add_run_to_campaign: add_campaign_event_id + add_run_event_id (2)
    # The Run seed uses a separately-allocated uuid4 (does not pull
    # from the queue) -- the helper passes it directly.
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            campaign_id,
            register_event_id,
            start_event_id,
            add_campaign_event_id,
            add_run_event_id,
        ],
    )

    # Register + Start Campaign.
    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="test campaign",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Seed a Run directly via event-store append.
    await _seed_run_via_event_store(deps, run_id, event_id=uuid4())

    # Add Run to Campaign.
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Campaign stream: 3 events (Registered + Started + RunAdded).
    campaign_events, campaign_version = await deps.event_store.load("Campaign", campaign_id)
    assert campaign_version == 3
    assert campaign_events[-1].event_type == "CampaignRunAdded"
    assert campaign_events[-1].payload["run_id"] == str(run_id)
    state = campaign_fold([campaign_from_stored(s) for s in campaign_events])
    assert state is not None
    assert run_id in state.run_ids

    # Run stream: 2 events (Started + AddedToCampaign).
    run_events, run_version = await deps.event_store.load("Run", run_id)
    assert run_version == 2
    assert run_events[-1].event_type == "RunAddedToCampaign"
    assert run_events[-1].payload["campaign_id"] == str(campaign_id)
    run_state = run_fold([run_from_stored(s) for s in run_events])
    assert run_state is not None
    assert run_state.campaign_id == campaign_id

    # Atomic xid8 invariant: Campaign's CampaignRunAdded + Run's
    # RunAddedToCampaign share the same transaction_id.
    assert campaign_events[-1].transaction_id == run_events[-1].transaction_id


@pytest.mark.integration
async def test_add_run_to_campaign_bumps_run_count_after_drain(
    db_pool: asyncpg.Pool,
) -> None:
    """Projection: after add_run + drain, proj_campaign_summary
    has run_count=1 for the Campaign."""
    campaign_id = uuid4()
    run_id = uuid4()
    lead = uuid4()

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(6)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="run-count test",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _seed_run_via_event_store(deps, run_id, event_id=uuid4())
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT run_count FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["run_count"] == 1


# ---------- N3: NO CASCADE anti-hook ----------


@pytest.mark.integration
@pytest.mark.parametrize(
    "terminator",
    ["close", "abandon"],
    ids=["close", "abandon"],
)
async def test_campaign_state_change_does_not_cascade_to_member_run(
    db_pool: asyncpg.Pool,
    terminator: str,
) -> None:
    """Pin the NO CASCADE anti-hook at the integration layer.

    Per GLP §10.2.5, ISO 17025 §7.5, 21 CFR §11.10(e) (per-Run audit
    independence) + the PAS-X cascading-holds war story: Campaign
    state changes (hold / close / abandon) MUST NOT modify member Run
    state. We snapshot the Run's stream length + last event before
    the Campaign-side transition, fire the transition, then re-load
    the Run and assert nothing on the Run stream changed.
    """
    campaign_id = uuid4()
    run_id = uuid4()
    lead = uuid4()

    # 7 ids: campaign_id + register_event + start_event + add_campaign_event
    # + add_run_event + hold/abandon/close_event + (one spare for the
    # FixedIdGenerator since hold also consumes an event id).
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(8)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="no-cascade test",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _seed_run_via_event_store(deps, run_id, event_id=uuid4())
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Snapshot Run state BEFORE the Campaign-side terminal transition.
    run_events_before, run_version_before = await deps.event_store.load("Run", run_id)
    run_state_before = run_fold([run_from_stored(s) for s in run_events_before])
    assert run_state_before is not None

    # Fire the Campaign-side terminator.
    if terminator == "close":
        await close_campaign.bind(deps)(
            CloseCampaign(campaign_id=campaign_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    else:  # abandon
        await abandon_campaign.bind(deps)(
            AbandonCampaign(campaign_id=campaign_id, reason="no-cascade integration check"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # NO CASCADE: Run stream length + Run.status unchanged.
    run_events_after, run_version_after = await deps.event_store.load("Run", run_id)
    assert run_version_after == run_version_before, (
        f"NO CASCADE violated: Run stream length changed from "
        f"{run_version_before} to {run_version_after} after campaign-{terminator}"
    )
    run_state_after = run_fold([run_from_stored(s) for s in run_events_after])
    assert run_state_after is not None
    assert run_state_after.status == run_state_before.status, (
        f"NO CASCADE violated: Run.status changed from "
        f"{run_state_before.status} to {run_state_after.status} after campaign-{terminator}"
    )


@pytest.mark.integration
async def test_campaign_hold_does_not_cascade_to_member_run(
    db_pool: asyncpg.Pool,
) -> None:
    """NO CASCADE on the non-terminal Held transition too.

    Membership stays addable in Held per design memo; this test pins
    that the Held transition itself does not touch member Run state.
    """
    campaign_id = uuid4()
    run_id = uuid4()
    lead = uuid4()

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(8)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="no-cascade-hold test",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _seed_run_via_event_store(deps, run_id, event_id=uuid4())
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    run_events_before, run_version_before = await deps.event_store.load("Run", run_id)

    await hold_campaign.bind(deps)(
        HoldCampaign(campaign_id=campaign_id, reason="paused for nightly cooldown"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    run_events_after, run_version_after = await deps.event_store.load("Run", run_id)
    assert run_version_after == run_version_before
    assert len(run_events_after) == len(run_events_before)


# ---------- N6: membership chain settles at run_count == 2 ----------


@pytest.mark.integration
async def test_membership_chain_run_count_settles_at_two(
    db_pool: asyncpg.Pool,
) -> None:
    """Add 3 Runs, remove 1 (with reason); projection settles at 2.

    Pins the additive/decremental run_count denorm round-trip across
    a non-trivial membership sequence. Each add_run + remove_run is a
    cross-aggregate `append_streams` call; the projection worker
    drains the events in order.
    """
    campaign_id = uuid4()
    run_ids = [uuid4() for _ in range(3)]
    lead = uuid4()

    # IDs consumed: campaign_id + register_event + start_event
    #   + 3 * (add_campaign_event + add_run_event)
    #   + 1 * (remove_campaign_event + remove_run_event)
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(20)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="membership chain",
            intent=CampaignIntent.BLOCK,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    for run_id in run_ids:
        await _seed_run_via_event_store(deps, run_id, event_id=uuid4())
        await add_run_to_campaign.bind(deps)(
            AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    # Remove the first member (reason required by the slice's VO).
    await remove_run_from_campaign.bind(deps)(
        RemoveRunFromCampaign(
            campaign_id=campaign_id,
            run_id=run_ids[0],
            reason="reassigned to a parallel campaign",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await _drain(db_pool)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT run_count FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["run_count"] == 2


# ---------- Concurrent membership: gather + forced ConcurrencyError (Watch #15) ----------


@pytest.mark.integration
async def test_concurrent_add_runs_to_same_campaign_settle_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    """asyncio.gather on two add_run_to_campaign calls for the same
    Campaign + different Runs: under true parallelism one call may lose
    the optimistic-version race and raise ConcurrencyError, which the
    operator (or a calling saga) is expected to retry. This test pins
    that contract end-to-end: both Runs land as members via the
    documented retry path, never via a lucky no-conflict shape.

    Earlier shipped as `xfail strict=False` per Watch #15 deferral.
    The forced-version-conflict sibling test
    (`test_forced_concurrent_add_runs_raises_concurrency_error`) pins
    the OCC failure-on-first-attempt path explicitly; this test pins
    the operator-retries-and-both-land convergent path.
    """
    import asyncio

    from cora.infrastructure.ports.event_store import ConcurrencyError

    campaign_id = uuid4()
    run_ids = [uuid4(), uuid4()]
    lead = uuid4()

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(12)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="concurrent race",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    for run_id in run_ids:
        await _seed_run_via_event_store(deps, run_id, event_id=uuid4())

    add = add_run_to_campaign.bind(deps)

    async def _add_with_retry(run_id: UUID) -> None:
        for _attempt in range(3):
            try:
                await add(
                    AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
                    principal_id=_PRINCIPAL_ID,
                    correlation_id=_CORRELATION_ID,
                )
                return
            except ConcurrencyError:
                continue
        msg = f"add_run_to_campaign(run={run_id}) did not settle after 3 retries"
        raise AssertionError(msg)

    await asyncio.gather(*[_add_with_retry(rid) for rid in run_ids])

    # End-state: both Runs landed as Campaign members. Single-pool
    # asyncio serialization makes this the realistic semantic today;
    # if a future change introduces true parallelism (multi-connection
    # pool + worker processes), one call would ConcurrencyError on
    # expected_version and require operator-side retry — the
    # forced-conflict sibling test pins that path.
    campaign_events, _ = await deps.event_store.load("Campaign", campaign_id)
    member_run_ids = {
        UUID(e.payload["run_id"]) for e in campaign_events if e.event_type == "CampaignRunAdded"
    }
    assert member_run_ids == set(run_ids)


@pytest.mark.integration
async def test_forced_concurrent_add_runs_raises_concurrency_error(
    db_pool: asyncpg.Pool,
) -> None:
    """Forces the OCC failure path the gather-race test cannot reliably
    induce under shared-pool serialization. Bypasses the handler's
    load step: pre-loads campaign + run versions ONCE, then constructs
    two append_streams batches both claiming the same expected_version
    on the Campaign stream. The second commit MUST raise
    ConcurrencyError; the first commits cleanly.

    This pins the multi-stream OCC invariant directly (Watch #15
    primary obligation). Combined with the gather-race test above:
    happy serialization path proven AND failure path proven.
    """
    from cora.campaign.aggregates.campaign import (
        CampaignRunAdded,
    )
    from cora.campaign.aggregates.campaign import (
        event_type_name as campaign_event_type_name,
    )
    from cora.campaign.aggregates.campaign import (
        to_payload as campaign_to_payload,
    )
    from cora.infrastructure.event_envelope import to_new_event
    from cora.infrastructure.ports.event_store import ConcurrencyError, StreamAppend
    from cora.run.aggregates.run import (
        RunAddedToCampaign,
    )
    from cora.run.aggregates.run import (
        event_type_name as run_event_type_name,
    )
    from cora.run.aggregates.run import (
        to_payload as run_to_payload,
    )

    campaign_id = uuid4()
    run_a_id = uuid4()
    run_b_id = uuid4()
    lead = uuid4()

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(10)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="forced conflict",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _seed_run_via_event_store(deps, run_a_id, event_id=uuid4())
    await _seed_run_via_event_store(deps, run_b_id, event_id=uuid4())

    # Load Campaign once; capture stale version that both batches will
    # claim. This is the canonical "two operators read at the same
    # version, both try to commit" pattern.
    _, stale_campaign_version = await deps.event_store.load("Campaign", campaign_id)
    _, run_a_version = await deps.event_store.load("Run", run_a_id)
    _, run_b_version = await deps.event_store.load("Run", run_b_id)

    def _build_batch(run_id: UUID, run_version: int) -> list[StreamAppend]:
        campaign_event = CampaignRunAdded(
            campaign_id=campaign_id,
            run_id=run_id,
            occurred_at=_NOW,
        )
        run_event = RunAddedToCampaign(
            run_id=run_id,
            campaign_id=campaign_id,
            occurred_at=_NOW,
        )
        return [
            StreamAppend(
                stream_type="Campaign",
                stream_id=campaign_id,
                expected_version=stale_campaign_version,
                events=[
                    to_new_event(
                        event_type=campaign_event_type_name(campaign_event),
                        payload=campaign_to_payload(campaign_event),
                        occurred_at=campaign_event.occurred_at,
                        event_id=uuid4(),
                        command_name="AddRunToCampaign",
                        correlation_id=_CORRELATION_ID,
                        principal_id=_PRINCIPAL_ID,
                    )
                ],
            ),
            StreamAppend(
                stream_type="Run",
                stream_id=run_id,
                expected_version=run_version,
                events=[
                    to_new_event(
                        event_type=run_event_type_name(run_event),
                        payload=run_to_payload(run_event),
                        occurred_at=run_event.occurred_at,
                        event_id=uuid4(),
                        command_name="AddRunToCampaign",
                        correlation_id=_CORRELATION_ID,
                        principal_id=_PRINCIPAL_ID,
                    )
                ],
            ),
        ]

    # First commit: succeeds, bumps Campaign version stale -> stale+1.
    await deps.event_store.append_streams(_build_batch(run_a_id, run_a_version))

    # Second commit: still claims the original stale_campaign_version,
    # which no longer matches Campaign's actual version. The multi-
    # stream OCC contract MUST raise ConcurrencyError.
    with pytest.raises(ConcurrencyError) as exc_info:
        await deps.event_store.append_streams(_build_batch(run_b_id, run_b_version))

    assert exc_info.value.stream_type == "Campaign"
    assert exc_info.value.expected == stale_campaign_version
    assert exc_info.value.actual == stale_campaign_version + 1

    # End-state: only run_a landed as member (the failing batch rolled
    # back atomically; Run B stream version is unchanged).
    campaign_events, _ = await deps.event_store.load("Campaign", campaign_id)
    member_run_ids = {
        UUID(e.payload["run_id"]) for e in campaign_events if e.event_type == "CampaignRunAdded"
    }
    assert member_run_ids == {run_a_id}

    _, post_run_b_version = await deps.event_store.load("Run", run_b_id)
    assert post_run_b_version == run_b_version, (
        "Failed batch must NOT have committed to Run B's stream (atomic rollback)"
    )

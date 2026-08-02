"""End-to-end PG integration test: `remove_run_from_campaign` two-stream atomic.

Mirrors test_add_run_to_campaign_postgres.py shape but exercises the
inverse path: pre-add a Run to a Campaign, then remove it. Asserts:

  - Campaign's run_ids loses the run_id.
  - Run.campaign_id clears back to None.
  - Both stream version cursors advance in a single transaction.
  - proj_campaign_summary.run_count decrements after drain.
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
    add_run_to_campaign,
    register_campaign,
    remove_run_from_campaign,
    start_campaign,
)
from cora.campaign.features.add_run_to_campaign import AddRunToCampaign
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

_NOW = datetime(2026, 5, 17, 13, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed_run(deps, run_id: UUID, *, event_id: UUID) -> None:
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
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_campaign_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


@pytest.mark.integration
async def test_remove_run_from_campaign_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    campaign_id = uuid4()
    run_id = uuid4()
    lead = uuid4()

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(10)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="remove test",
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
    await _seed_run(deps, run_id, event_id=uuid4())
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Remove the Run.
    await remove_run_from_campaign.bind(deps)(
        RemoveRunFromCampaign(
            campaign_id=campaign_id,
            run_id=run_id,
            reason="reassigned to a follow-on campaign",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Campaign: 4 events (Registered + Started + RunAdded + RunRemoved).
    campaign_events, campaign_version = await deps.event_store.load("Campaign", campaign_id)
    assert campaign_version == 4
    assert campaign_events[-1].event_type == "CampaignRunRemoved"
    assert campaign_events[-1].payload["reason"] == "reassigned to a follow-on campaign"
    state = campaign_fold([campaign_from_stored(s) for s in campaign_events])
    assert state is not None
    assert run_id not in state.run_ids

    # Run: 3 events (Started + AddedToCampaign + RemovedFromCampaign).
    run_events, run_version = await deps.event_store.load("Run", run_id)
    assert run_version == 3
    assert run_events[-1].event_type == "RunRemovedFromCampaign"
    assert run_events[-1].payload["reason"] == "reassigned to a follow-on campaign"
    run_state = run_fold([run_from_stored(s) for s in run_events])
    assert run_state is not None
    assert run_state.campaign_id is None

    # Atomic xid8 invariant on the remove transaction.
    assert campaign_events[-1].transaction_id == run_events[-1].transaction_id


@pytest.mark.integration
async def test_remove_run_decrements_run_count_after_drain(
    db_pool: asyncpg.Pool,
) -> None:
    campaign_id = uuid4()
    run_id = uuid4()
    lead = uuid4()

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[campaign_id] + [uuid4() for _ in range(10)],
    )

    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="remove + projection",
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
    await _seed_run(deps, run_id, event_id=uuid4())
    await add_run_to_campaign.bind(deps)(
        AddRunToCampaign(campaign_id=campaign_id, run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await remove_run_from_campaign.bind(deps)(
        RemoveRunFromCampaign(
            campaign_id=campaign_id,
            run_id=run_id,
            reason="removed",
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
    assert row["run_count"] == 0

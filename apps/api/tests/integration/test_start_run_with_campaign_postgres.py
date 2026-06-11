"""End-to-end PG integration test: `start_run` with `campaign_id`
performs the cross-aggregate atomic write (Run stream + Campaign
stream) via `EventStore.append_streams`.

Mirrors `test_start_run_handler_postgres.py` for the upstream chain
+ adds a Campaign + asserts the at-start membership write reflects
on both streams + the run_count projection denorm.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingParameterType=false

from datetime import UTC, datetime
from uuid import UUID

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
from cora.campaign.features import register_campaign, start_campaign
from cora.campaign.features.register_campaign import RegisterCampaign
from cora.campaign.features.start_campaign import StartCampaign
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import load_run
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0dc85")


async def _drain(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_campaign_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


@pytest.mark.integration
async def test_start_run_with_campaign_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    # Carefully-allocated id queue (start_run pre-loads, then needs
    # 1 run id + 2 event ids when campaign_id is set: RunStarted
    # event id + CampaignRunAdded event id).
    cap_id = UUID("01900000-0000-7000-8000-00000071aa01")
    cap_event_id = UUID("01900000-0000-7000-8000-00000071aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000071ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000071ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000071ab03")
    method_id = UUID("01900000-0000-7000-8000-00000071ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000071ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000071ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000071ad02")
    site_id = UUID("01900000-0000-7000-8000-00000071ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000071af01")
    plan_event_id = UUID("01900000-0000-7000-8000-00000071af02")
    subject_id = UUID("01900000-0000-7000-8000-00000071b001")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000071b002")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000071b003")
    campaign_id = UUID("01900000-0000-7000-8000-00000071c001")
    campaign_register_event_id = UUID("01900000-0000-7000-8000-00000071c002")
    campaign_start_event_id = UUID("01900000-0000-7000-8000-00000071c003")
    run_id = UUID("01900000-0000-7000-8000-00000071d001")
    run_event_id = UUID("01900000-0000-7000-8000-00000071d002")
    campaign_run_added_event_id = UUID("01900000-0000-7000-8000-00000071d003")
    lead_actor_id = UUID("01900000-0000-7000-8000-00000071e001")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            cap_id,
            cap_event_id,
            asset_id,
            asset_register_event_id,
            asset_addcap_event_id,
            method_id,
            method_event_id,
            practice_id,
            practice_event_id,
            plan_id,
            plan_event_id,
            subject_id,
            subject_register_event_id,
            subject_mount_event_id,
            campaign_id,
            campaign_register_event_id,
            campaign_start_event_id,
            run_id,
            run_event_id,
            campaign_run_added_event_id,
        ],
    )

    # Upstream chain.
    await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    await define_method.bind(deps)(
        DefineMethod(
            capability_id=_CAPABILITY_ID, name="XRF Fly Scan", needed_family_ids=frozenset({cap_id})
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_practice.bind(deps)(
        DefinePractice(name="APS XRF", method_id=method_id, site_id=site_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await define_plan.bind(deps)(
        DefinePlan(
            name="32-ID FlyScan",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_subject.bind(deps)(
        RegisterSubject(name="PorousCeramicSample-A"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason=""),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Active Campaign.
    await register_campaign.bind(deps)(
        RegisterCampaign(
            name="campaign-at-start",
            intent=CampaignIntent.SERIES,
            lead_actor_id=lead_actor_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await start_campaign.bind(deps)(
        StartCampaign(campaign_id=campaign_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Start Run with campaign_id.
    returned_id = await start_run.bind(deps)(
        StartRun(
            name="campaign-bound at-start run",
            plan_id=plan_id,
            subject_id=subject_id,
            campaign_id=campaign_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == run_id

    # Run stream: RunStarted carries campaign_id.
    run_events, run_version = await deps.event_store.load("Run", run_id)
    assert run_version == 1
    assert run_events[0].event_type == "RunStarted"
    assert run_events[0].payload["campaign_id"] == str(campaign_id)

    # Run.campaign_id reflects on aggregate state.
    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.campaign_id == campaign_id

    # Campaign stream: 3 events (Registered + Started + RunAdded).
    campaign_events, campaign_version = await deps.event_store.load("Campaign", campaign_id)
    assert campaign_version == 3
    assert campaign_events[-1].event_type == "CampaignRunAdded"
    assert campaign_events[-1].payload["run_id"] == str(run_id)
    campaign_state = campaign_fold([campaign_from_stored(s) for s in campaign_events])
    assert campaign_state is not None
    assert run_id in campaign_state.run_ids

    # Atomic xid8 invariant: the RunStarted + CampaignRunAdded events
    # share the same Postgres transaction (single append_streams call).
    assert run_events[0].transaction_id == campaign_events[-1].transaction_id

    # Projection: run_count = 1 after drain.
    await _drain(db_pool)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT run_count FROM proj_campaign_summary WHERE campaign_id = $1",
            campaign_id,
        )
    assert row is not None
    assert row["run_count"] == 1

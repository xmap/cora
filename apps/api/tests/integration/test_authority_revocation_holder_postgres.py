"""End-to-end integration: the kill-switch (K1 + K2 + K3) against real Postgres.

Exercises the whole chain: a principal starts a real Run (RunStarted envelope
principal == that principal), K2's involvement projection folds it, a
PolicyGrantRevoked (K1's trigger) is issued, and draining K2's projection + the
K3 holder subscriber together holds the run and records a Decision.

Pins:
  - a Running run STARTED by the revoked principal is held (RunHeld persisted,
    aggregate folds to Held) and a Decision(context=AuthorityRevocationHold,
    choice=Held) is written, parented to the revocation event.
  - a run started by a DIFFERENT principal is left Running (kind-blind attribution
    is by starter, not a blanket hold).
  - the hold uses the aggregate's Running-only guard (an already-held run -> the
    holder records HoldDeferred, no crash, status unchanged).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.agent.seed_authority_revocation_holder import seed_authority_revocation_holder_agent
from cora.agent.subscribers.authority_revocation_holder import (
    _derive_decision_id,
    make_authority_revocation_holder_subscriber,
)
from cora.decision.aggregates.decision import load_decision
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.features import add_asset_family, define_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports import UUIDv7Generator
from cora.infrastructure.ports.event_store import StoredEvent
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features import define_method, define_plan, define_practice
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.adapters import PostgresRunActorInvolvementLookup
from cora.run.aggregates.run import RunStatus, load_run
from cora.run.features import start_run
from cora.run.features.hold_run import HoldRun
from cora.run.features.hold_run import bind as bind_hold_run
from cora.run.features.start_run import StartRun
from cora.run.projections import RunActorInvolvementProjection
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 7, 6, 12, 0, 0, tzinfo=UTC)
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


def _deps(db_pool: asyncpg.Pool) -> Kernel:
    """Kernel with a UUIDv7 id generator (the genesis chain mints many ids) and the
    real Postgres involvement lookup wired, so the K3 holder reads K2's projection."""
    return build_postgres_deps(
        db_pool,
        now=_NOW,
        id_generator=UUIDv7Generator(),
        run_actor_involvement_lookup=PostgresRunActorInvolvementLookup(db_pool),
    )


async def _start_run_as(deps: Kernel, *, starter: UUID, tag: str) -> UUID:
    """Seed the upstream chain and start one Run as `starter`; return its run_id.

    Each call uses fresh streams (distinct Family name per tag) so runs are
    independent. The RunStarted envelope principal is `starter`, which is what K2
    attributes on.
    """
    family_id = await define_family.bind(deps)(
        DefineFamily(name=f"FlyMotion-{tag}", affordances=frozenset()),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name=f"EigerDetector-{tag}", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    cap_event_id = uuid4()
    await seed_capability_postgres(deps.event_store, cap_event_id)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=cap_event_id,
            name=f"XRF Fly Scan {tag}",
            needed_family_ids=frozenset({family_id}),
        ),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name=f"APS XRF {tag}", method_id=method_id, site_id=uuid4()),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(
            name=f"32-ID FlyScan {tag}",
            practice_id=practice_id,
            asset_ids=frozenset({asset_id}),
        ),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name=f"PorousCeramicSample-{tag}"),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, asset_id=uuid4(), now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason=""),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )
    return await start_run.bind(deps)(
        StartRun(name=f"session {tag}", plan_id=plan_id, subject_id=subject_id),
        principal_id=starter,
        correlation_id=_CORRELATION_ID,
    )


def _revocation_event(*, revoked_principal_id: UUID) -> StoredEvent:
    """Build a PolicyGrantRevoked (K1 trigger) as a StoredEvent.

    Delivered to the subscriber via a direct `apply()` call, matching the
    established subscriber-integration-test convention (RunDebriefer /
    CautionDrafter tests apply() directly rather than going through the
    projection-worker drain, which requires a seeded bookmark row)."""
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
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        occurred_at=_NOW,
        recorded_at=_NOW,
        principal_id=uuid4(),
    )


async def _drain_involvement(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    registry.register(RunActorInvolvementProjection())
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _run_holder(deps: Kernel, event: StoredEvent) -> None:
    """Deliver one revocation event to the holder subscriber via direct apply()."""
    holder = make_authority_revocation_holder_subscriber(deps)
    await holder.apply(event, conn=None)  # type: ignore[arg-type]


@pytest.mark.integration
async def test_revoke_holds_the_revoked_principals_running_run(db_pool: asyncpg.Pool) -> None:
    deps = _deps(db_pool)
    await seed_authority_revocation_holder_agent(deps)

    revoked = uuid4()
    run_id = await _start_run_as(deps, starter=revoked, tag="revoked")
    await _drain_involvement(db_pool)

    event = _revocation_event(revoked_principal_id=revoked)
    await _run_holder(deps, event)

    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.HELD

    decision = await load_decision(deps.event_store, _derive_decision_id(event.event_id, run_id))
    assert decision is not None
    assert decision.choice.value == "Held"
    assert decision.parent_id == event.event_id


@pytest.mark.integration
async def test_revoke_leaves_other_principals_run_running(db_pool: asyncpg.Pool) -> None:
    deps = _deps(db_pool)
    await seed_authority_revocation_holder_agent(deps)

    revoked = uuid4()
    other = uuid4()
    revoked_run = await _start_run_as(deps, starter=revoked, tag="rev")
    other_run = await _start_run_as(deps, starter=other, tag="other")
    await _drain_involvement(db_pool)

    await _run_holder(deps, _revocation_event(revoked_principal_id=revoked))

    revoked_state = await load_run(deps.event_store, revoked_run)
    other_state = await load_run(deps.event_store, other_run)
    assert revoked_state is not None and revoked_state.status is RunStatus.HELD
    assert other_state is not None and other_state.status is RunStatus.RUNNING


@pytest.mark.integration
async def test_already_held_run_folds_to_hold_deferred(db_pool: asyncpg.Pool) -> None:
    deps = _deps(db_pool)
    await seed_authority_revocation_holder_agent(deps)

    revoked = uuid4()
    run_id = await _start_run_as(deps, starter=revoked, tag="held")
    # Operator-hold it first, so the holder's own hold hits the Running-only guard.
    await bind_hold_run(deps)(
        HoldRun(run_id=run_id),
        principal_id=revoked,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_involvement(db_pool)

    event = _revocation_event(revoked_principal_id=revoked)
    await _run_holder(deps, event)

    state = await load_run(deps.event_store, run_id)
    assert state is not None and state.status is RunStatus.HELD
    decision = await load_decision(deps.event_store, _derive_decision_id(event.event_id, run_id))
    assert decision is not None
    assert decision.choice.value == "HoldDeferred"

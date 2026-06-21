"""Unit tests for the `start_run` application handler.

This handler pre-loads the full upstream chain — Plan → Practice →
Method → each bound Asset → Subject (if subject_id given) — before
reaching the pure decider. Second instance of the cross-aggregate-
validation pattern (after `define_plan`).

Test setup uses direct event-seeding helpers via `_seed_*`
functions that append events directly to the in-memory store,
bypassing the upstream BCs' handlers. Mirrors
test_define_plan_handler.py's seeding approach. Keeps the test
focus on start_run handler behavior, not upstream BC behavior.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    AssetNotFoundError,
    AssetTier,
)
from cora.equipment.aggregates.asset.events import (
    AssetFamilyAdded,
    AssetRegistered,
)
from cora.equipment.aggregates.asset.events import (
    event_type_name as asset_event_type_name,
)
from cora.equipment.aggregates.asset.events import (
    to_payload as asset_to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.recipe.aggregates.method import MethodNotFoundError
from cora.recipe.aggregates.method.events import MethodDefined
from cora.recipe.aggregates.method.events import (
    event_type_name as method_event_type_name,
)
from cora.recipe.aggregates.method.events import to_payload as method_to_payload
from cora.recipe.aggregates.plan import PlanNotFoundError
from cora.recipe.aggregates.plan.events import PlanDefined, PlanDeprecated
from cora.recipe.aggregates.plan.events import (
    event_type_name as plan_event_type_name,
)
from cora.recipe.aggregates.plan.events import to_payload as plan_to_payload
from cora.recipe.aggregates.practice import PracticeNotFoundError
from cora.recipe.aggregates.practice.events import PracticeDefined
from cora.recipe.aggregates.practice.events import (
    event_type_name as practice_event_type_name,
)
from cora.recipe.aggregates.practice.events import (
    to_payload as practice_to_payload,
)
from cora.run import RunHandlers, UnauthorizedError, wire_run
from cora.run.aggregates.run import (
    RunBeamAvailabilityUnknownError,
    RunBoundPlanDeprecatedError,
    RunCapabilitiesNotSatisfiedError,
    RunPlanAssetDecommissionedError,
    RunRequiresOpenBeamShuttersError,
    RunSubjectNotMountableError,
)
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.shared.identity import ActorId
from cora.subject.aggregates.subject import SubjectNotFoundError
from cora.subject.aggregates.subject.events import (
    SubjectMounted,
    SubjectRegistered,
)
from cora.subject.aggregates.subject.events import (
    event_type_name as subject_event_type_name,
)
from cora.subject.aggregates.subject.events import (
    to_payload as subject_to_payload,
)
from tests.unit._helpers import build_deps

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-000000000f01")
_EVENT_ID = UUID("01900000-0000-7000-8000-000000000f02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


# ---------- Direct event-seeding helpers ----------


async def _append(
    store: InMemoryEventStore,
    *,
    stream_type: str,
    stream_id: UUID,
    expected_version: int,
    event_type: str,
    payload: dict[str, object],
    command_name: str,
) -> None:
    new_event = to_new_event(
        event_type=event_type,
        payload=payload,
        occurred_at=_NOW,
        event_id=uuid4(),
        command_name=command_name,
        correlation_id=_CORRELATION_ID,
        principal_id=uuid4(),
    )
    await store.append(
        stream_type=stream_type,
        stream_id=stream_id,
        expected_version=expected_version,
        events=[new_event],
    )


async def _seed_method(
    store: InMemoryEventStore,
    method_id: UUID,
    *,
    needed_family_ids: frozenset[UUID] = frozenset(),
) -> None:
    event = MethodDefined(
        method_id=method_id,
        name="Test Method",
        needed_family_ids=tuple(sorted(needed_family_ids, key=str)),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Method",
        stream_id=method_id,
        expected_version=0,
        event_type=method_event_type_name(event),
        payload=method_to_payload(event),
        command_name="DefineMethod",
    )


async def _seed_practice(
    store: InMemoryEventStore,
    practice_id: UUID,
    *,
    method_id: UUID,
) -> None:
    event = PracticeDefined(
        practice_id=practice_id,
        name="Test Practice",
        method_id=method_id,
        site_id=uuid4(),
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Practice",
        stream_id=practice_id,
        expected_version=0,
        event_type=practice_event_type_name(event),
        payload=practice_to_payload(event),
        command_name="DefinePractice",
    )


async def _seed_asset(
    store: InMemoryEventStore,
    asset_id: UUID,
    *,
    capabilities: frozenset[UUID] = frozenset(),
    decommissioned: bool = False,
) -> None:
    register_event = AssetRegistered(
        asset_id=asset_id,
        name="TestAsset",
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        occurred_at=_NOW,
        commissioned_by=ActorId(uuid4()),
    )
    await _append(
        store,
        stream_type="Asset",
        stream_id=asset_id,
        expected_version=0,
        event_type=asset_event_type_name(register_event),
        payload=asset_to_payload(register_event),
        command_name="RegisterAsset",
    )
    version = 1
    for cap_id in sorted(capabilities, key=str):
        cap_event = AssetFamilyAdded(asset_id=asset_id, family_id=cap_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(cap_event),
            payload=asset_to_payload(cap_event),
            command_name="AddAssetFamily",
        )
        version += 1
    if decommissioned:
        from cora.equipment.aggregates.asset.events import AssetDecommissioned

        dc_event = AssetDecommissioned(
            asset_id=asset_id, occurred_at=_NOW, decommissioned_by=ActorId(uuid4())
        )
        await _append(
            store,
            stream_type="Asset",
            stream_id=asset_id,
            expected_version=version,
            event_type=asset_event_type_name(dc_event),
            payload=asset_to_payload(dc_event),
            command_name="DecommissionAsset",
        )


async def _seed_plan(
    store: InMemoryEventStore,
    plan_id: UUID,
    *,
    practice_id: UUID,
    asset_ids: tuple[UUID, ...],
    method_id: UUID,
    deprecated: bool = False,
) -> None:
    event = PlanDefined(
        plan_id=plan_id,
        name="Test Plan",
        practice_id=practice_id,
        asset_ids=tuple(sorted(asset_ids, key=str)),
        method_id=method_id,
        method_needed_family_ids_snapshot=(),
        asset_families_snapshot={},
        occurred_at=_NOW,
    )
    await _append(
        store,
        stream_type="Plan",
        stream_id=plan_id,
        expected_version=0,
        event_type=plan_event_type_name(event),
        payload=plan_to_payload(event),
        command_name="DefinePlan",
    )
    if deprecated:
        deprecated_event = PlanDeprecated(plan_id=plan_id, occurred_at=_NOW)
        await _append(
            store,
            stream_type="Plan",
            stream_id=plan_id,
            expected_version=1,
            event_type=plan_event_type_name(deprecated_event),
            payload=plan_to_payload(deprecated_event),
            command_name="DeprecatePlan",
        )


async def _seed_subject_mounted(
    store: InMemoryEventStore,
    subject_id: UUID,
) -> None:
    register_event = SubjectRegistered(
        subject_id=subject_id, name="TestSubject", occurred_at=_NOW, registered_by=ActorId(uuid4())
    )
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=0,
        event_type=subject_event_type_name(register_event),
        payload=subject_to_payload(register_event),
        command_name="RegisterSubject",
    )
    mount_event = SubjectMounted(
        subject_id=subject_id,
        asset_id=uuid4(),
        reason="",
        occurred_at=_NOW,
        mounted_by=ActorId(uuid4()),
    )
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=1,
        event_type=subject_event_type_name(mount_event),
        payload=subject_to_payload(mount_event),
        command_name="MountSubject",
    )


async def seed_full_chain(
    store: InMemoryEventStore,
    *,
    plan_deprecated: bool = False,
    asset_decommissioned: bool = False,
    drift_capability_off_asset: bool = False,
) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID]:
    """Seed Family → Asset (with capability) → Method → Practice → Plan
    + Subject. Returns (cap_id, asset_id, method_id, practice_id, plan_id,
    subject_id). Subject is always Mounted; tests can override.

    Set `drift_capability_off_asset=True` to seed an Asset whose
    capabilities don't satisfy the Method's needs (simulates drift
    since Plan-bind).
    """
    cap_id = uuid4()
    asset_id = uuid4()
    method_id = uuid4()
    practice_id = uuid4()
    plan_id = uuid4()
    subject_id = uuid4()

    asset_caps: frozenset[UUID] = frozenset() if drift_capability_off_asset else frozenset({cap_id})
    await _seed_asset(store, asset_id, capabilities=asset_caps, decommissioned=asset_decommissioned)
    await _seed_method(store, method_id, needed_family_ids=frozenset({cap_id}))
    await _seed_practice(store, practice_id, method_id=method_id)
    await _seed_plan(
        store,
        plan_id,
        practice_id=practice_id,
        asset_ids=(asset_id,),
        method_id=method_id,
        deprecated=plan_deprecated,
    )
    await _seed_subject_mounted(store, subject_id)
    return (cap_id, asset_id, method_id, practice_id, plan_id, subject_id)


# ---------- Happy paths ----------


@pytest.mark.unit
async def test_handler_returns_generated_run_id_for_sample_run() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Run-A", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_returns_generated_run_id_for_dark_field_run() -> None:
    """Run without Subject (calibration / dark-field)."""
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Dark field", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID


@pytest.mark.unit
async def test_handler_appends_run_started_event_to_store() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    await handler(
        StartRun(name="Run-A", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await store.load("Run", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RunStarted"
    assert stored.payload["run_id"] == str(_NEW_ID)
    assert stored.payload["name"] == "Run-A"
    assert stored.payload["plan_id"] == str(plan_id)
    assert stored.payload["subject_id"] == str(subject_id)
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "StartRun"}


@pytest.mark.unit
async def test_handler_appends_run_started_with_null_subject_for_dark_field() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    await handler(
        StartRun(name="Dark field", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await store.load("Run", _NEW_ID)
    assert events[0].payload["subject_id"] is None


# ---------- Authorization ----------


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, deny=True)
    handler = start_run.bind(deps)

    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            StartRun(name="X", plan_id=uuid4(), subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
async def test_handler_does_not_pre_load_when_denied() -> None:
    """Authorize runs BEFORE the cross-aggregate pre-loads."""
    store = InMemoryEventStore()
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store, deny=True)
    handler = start_run.bind(deps)

    with pytest.raises(UnauthorizedError):
        await handler(
            StartRun(name="X", plan_id=uuid4(), subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

    events, version = await store.load("Run", _NEW_ID)
    assert events == []
    assert version == 0


# ---------- Pre-load: NotFoundError paths ----------


@pytest.mark.unit
async def test_handler_raises_plan_not_found_when_plan_missing() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = start_run.bind(deps)

    missing_plan_id = uuid4()
    with pytest.raises(PlanNotFoundError):
        await handler(
            StartRun(name="X", plan_id=missing_plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_practice_not_found_when_referenced_practice_missing() -> None:
    """Plan references a practice_id that's not in the store (defensive corruption case)."""
    store = InMemoryEventStore()
    asset_id = uuid4()
    method_id = uuid4()
    plan_id = uuid4()
    bogus_practice_id = uuid4()
    await _seed_asset(store, asset_id, capabilities=frozenset())
    await _seed_method(store, method_id)
    # Plan references a practice that doesn't exist.
    await _seed_plan(
        store,
        plan_id,
        practice_id=bogus_practice_id,
        asset_ids=(asset_id,),
        method_id=method_id,
    )
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(PracticeNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_method_not_found_when_referenced_method_missing() -> None:
    store = InMemoryEventStore()
    asset_id = uuid4()
    practice_id = uuid4()
    plan_id = uuid4()
    bogus_method_id = uuid4()
    await _seed_asset(store, asset_id, capabilities=frozenset())
    await _seed_practice(store, practice_id, method_id=bogus_method_id)
    await _seed_plan(
        store,
        plan_id,
        practice_id=practice_id,
        asset_ids=(asset_id,),
        method_id=bogus_method_id,
    )
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(MethodNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_asset_not_found_when_bound_asset_missing() -> None:
    store = InMemoryEventStore()
    method_id = uuid4()
    practice_id = uuid4()
    plan_id = uuid4()
    bogus_asset_id = uuid4()
    await _seed_method(store, method_id)
    await _seed_practice(store, practice_id, method_id=method_id)
    # Plan references an Asset that doesn't exist.
    await _seed_plan(
        store,
        plan_id,
        practice_id=practice_id,
        asset_ids=(bogus_asset_id,),
        method_id=method_id,
    )
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(AssetNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_subject_not_found_when_subject_id_missing() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    bogus_subject_id = uuid4()
    with pytest.raises(SubjectNotFoundError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=bogus_subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Decider error propagation ----------


@pytest.mark.unit
async def test_handler_propagates_plan_deprecated_error() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await seed_full_chain(store, plan_deprecated=True)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(RunBoundPlanDeprecatedError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_subject_not_mountable_error() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    # Mounted Subject from seed_full_chain — let's flip it to Removed.
    from cora.subject.aggregates.subject.events import (
        SubjectMeasured,
        SubjectRemoved,
    )

    measured = SubjectMeasured(
        subject_id=subject_id, occurred_at=_NOW, measured_by=ActorId(uuid4())
    )
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=2,
        event_type=subject_event_type_name(measured),
        payload=subject_to_payload(measured),
        command_name="MeasureSubject",
    )
    removed = SubjectRemoved(subject_id=subject_id, occurred_at=_NOW, removed_by=ActorId(uuid4()))
    await _append(
        store,
        stream_type="Subject",
        stream_id=subject_id,
        expected_version=3,
        event_type=subject_event_type_name(removed),
        payload=subject_to_payload(removed),
        command_name="RemoveSubject",
    )
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(RunSubjectNotMountableError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_run_asset_decommissioned_error() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await seed_full_chain(store, asset_decommissioned=True)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(RunPlanAssetDecommissionedError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_propagates_capabilities_not_satisfied_at_run_start() -> None:
    """Re-validation: Asset capabilities drifted off after Plan-bind."""
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await seed_full_chain(store, drift_capability_off_asset=True)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(RunCapabilitiesNotSatisfiedError):
        await handler(
            StartRun(name="X", plan_id=plan_id, subject_id=None),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# ---------- Causation propagation ----------


@pytest.mark.unit
async def test_handler_propagates_causation_id_to_appended_event() -> None:
    causation = UUID("01900000-0000-7000-8000-0000000000bb")
    store = InMemoryEventStore()
    _, _, _, _, plan_id, _ = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    await handler(
        StartRun(name="X", plan_id=plan_id, subject_id=None),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
        causation_id=causation,
    )

    events, _ = await store.load("Run", _NEW_ID)
    assert events[0].causation_id == causation


# ---------- Wire smoke ----------


@pytest.mark.unit
def test_wire_run_returns_handlers_bundle() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_run(deps)
    assert isinstance(handlers, RunHandlers)
    assert callable(handlers.start_run)
    assert callable(handlers.get_run)


# ---------- start_run with campaign_id ----------


async def _seed_campaign_active(
    store: InMemoryEventStore, campaign_id: UUID, lead_actor_id: UUID
) -> None:
    """Seed Campaign in Active status (Registered + Started)."""
    from cora.campaign.aggregates.campaign.events import (
        CampaignRegistered,
        CampaignStarted,
    )
    from cora.campaign.aggregates.campaign.events import (
        event_type_name as campaign_event_type_name,
    )
    from cora.campaign.aggregates.campaign.events import (
        to_payload as campaign_to_payload,
    )

    events: list[tuple[object, str]] = [
        (
            CampaignRegistered(
                campaign_id=campaign_id,
                name="test",
                intent="Series",
                lead_actor_id=lead_actor_id,
                subject_id=None,
                description=None,
                tags=frozenset(),
                external_refs=frozenset(),
                external_id=None,
                occurred_at=_NOW,
            ),
            "RegisterCampaign",
        ),
        (CampaignStarted(campaign_id=campaign_id, occurred_at=_NOW), "StartCampaign"),
    ]
    for idx, (event, command_name) in enumerate(events):
        await _append(
            store,
            stream_type="Campaign",
            stream_id=campaign_id,
            expected_version=idx,
            event_type=campaign_event_type_name(event),  # type: ignore[arg-type]
            payload=campaign_to_payload(event),  # type: ignore[arg-type]
            command_name=command_name,
        )


async def _seed_campaign_closed(
    store: InMemoryEventStore, campaign_id: UUID, lead_actor_id: UUID
) -> None:
    """Seed Campaign in Closed terminal status."""
    from cora.campaign.aggregates.campaign.events import CampaignClosed
    from cora.campaign.aggregates.campaign.events import (
        event_type_name as campaign_event_type_name,
    )
    from cora.campaign.aggregates.campaign.events import (
        to_payload as campaign_to_payload,
    )

    await _seed_campaign_active(store, campaign_id, lead_actor_id)
    event = CampaignClosed(campaign_id=campaign_id, occurred_at=_NOW)
    await _append(
        store,
        stream_type="Campaign",
        stream_id=campaign_id,
        expected_version=2,
        event_type=campaign_event_type_name(event),  # type: ignore[arg-type]
        payload=campaign_to_payload(event),  # type: ignore[arg-type]
        command_name="CloseCampaign",
    )


@pytest.mark.unit
async def test_handler_with_campaign_writes_both_streams_atomically() -> None:
    """When StartRun.campaign_id provided, the handler writes
    RunStarted (with campaign_id) on the Run stream AND CampaignRunAdded
    on the Campaign stream via append_streams."""
    from cora.campaign.aggregates.campaign import fold as campaign_fold
    from cora.campaign.aggregates.campaign import from_stored as campaign_from_stored

    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    campaign_id = uuid4()
    lead = uuid4()
    await _seed_campaign_active(store, campaign_id, lead)

    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID, uuid4()],  # run-id + 2 event-ids
        now=_NOW,
        event_store=store,
    )
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(
            name="Member",
            plan_id=plan_id,
            subject_id=subject_id,
            campaign_id=campaign_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID

    # Run stream: RunStarted with campaign_id on payload.
    run_events, run_version = await store.load("Run", _NEW_ID)
    assert run_version == 1
    assert run_events[0].event_type == "RunStarted"
    assert run_events[0].payload["campaign_id"] == str(campaign_id)

    # Campaign stream: 2 seed events + the membership-add event.
    campaign_stored, campaign_version = await store.load("Campaign", campaign_id)
    assert campaign_version == 3
    assert campaign_stored[-1].event_type == "CampaignRunAdded"
    assert campaign_stored[-1].payload["run_id"] == str(_NEW_ID)
    state = campaign_fold([campaign_from_stored(s) for s in campaign_stored])
    assert state is not None
    assert _NEW_ID in state.run_ids


@pytest.mark.unit
async def test_handler_raises_campaign_not_found_when_campaign_missing() -> None:
    from cora.campaign.aggregates.campaign import CampaignNotFoundError

    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    bogus_campaign_id = uuid4()

    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    with pytest.raises(CampaignNotFoundError):
        await handler(
            StartRun(
                name="Run",
                plan_id=plan_id,
                subject_id=subject_id,
                campaign_id=bogus_campaign_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_raises_cannot_join_for_terminal_campaign() -> None:
    """Starting a Run into a Closed Campaign raises 409
    RunCannotJoinCampaignError."""
    from cora.run.aggregates.run import RunCannotJoinCampaignError

    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    campaign_id = uuid4()
    await _seed_campaign_closed(store, campaign_id, uuid4())

    deps = build_deps(
        ids=[_NEW_ID, _EVENT_ID, uuid4()],
        now=_NOW,
        event_store=store,
    )
    handler = start_run.bind(deps)

    with pytest.raises(RunCannotJoinCampaignError) as exc:
        await handler(
            StartRun(
                name="Run",
                plan_id=plan_id,
                subject_id=subject_id,
                campaign_id=campaign_id,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.campaign_status == "Closed"


@pytest.mark.unit
async def test_handler_without_campaign_id_uses_single_stream_append() -> None:
    """Backward-compat path. No campaign_id means the handler writes
    only the Run stream (single-stream append)."""
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)

    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Standalone", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID
    run_events, _ = await store.load("Run", _NEW_ID)
    assert run_events[0].payload.get("campaign_id") is None


# ---------- BEAM-1 beam-availability gate (handler threads the lookup) ----------


class _FixedBeamLookup:
    """Test BeamAvailabilityLookup returning a fixed reading.

    Proves the handler reads `deps.beam_availability_lookup` and threads
    its result into the decider's beam gate (the gate logic itself is
    covered by test_start_run_beam_gate_decider).
    """

    def __init__(self, reading: BeamAvailabilityLookupResult) -> None:
        self._reading = reading

    async def read(self) -> BeamAvailabilityLookupResult:
        return self._reading


@pytest.mark.unit
async def test_handler_raises_requires_open_beam_when_lookup_reports_closed_shutter() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    deps = replace(
        deps,
        beam_availability_lookup=_FixedBeamLookup(
            BeamAvailabilityLookupResult(
                fes_open=False, sbs_open=True, fes_permit=True, quality_ok=True
            )
        ),
    )
    handler = start_run.bind(deps)

    with pytest.raises(RunRequiresOpenBeamShuttersError) as exc_info:
        await handler(
            StartRun(name="Run-A", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.blocking == frozenset({"fes_open"})


@pytest.mark.unit
async def test_handler_raises_beam_unknown_when_lookup_reports_bad_quality() -> None:
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    deps = replace(
        deps,
        beam_availability_lookup=_FixedBeamLookup(
            BeamAvailabilityLookupResult(
                fes_open=True, sbs_open=True, fes_permit=True, quality_ok=False
            )
        ),
    )
    handler = start_run.bind(deps)

    with pytest.raises(RunBeamAvailabilityUnknownError):
        await handler(
            StartRun(name="Run-A", plan_id=plan_id, subject_id=subject_id),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.unit
async def test_handler_starts_when_lookup_reports_all_open() -> None:
    """Explicit open reading (not the default stub) passes the gate."""
    store = InMemoryEventStore()
    _, _, _, _, plan_id, subject_id = await seed_full_chain(store)
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW, event_store=store)
    deps = replace(
        deps,
        beam_availability_lookup=_FixedBeamLookup(
            BeamAvailabilityLookupResult(
                fes_open=True, sbs_open=True, fes_permit=True, quality_ok=True
            )
        ),
    )
    handler = start_run.bind(deps)

    result = await handler(
        StartRun(name="Run-A", plan_id=plan_id, subject_id=subject_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert result == _NEW_ID

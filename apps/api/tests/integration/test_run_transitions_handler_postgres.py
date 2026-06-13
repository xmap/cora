"""End-to-end integration tests: complete_run / abort_run against real Postgres.

Round-trips for the two terminal transitions:
  - complete_run: full upstream chain + start + complete + load_run
    returns the Completed state with all bound refs preserved.
  - abort_run:    full upstream chain + start + abort + load_run
    returns the Aborted state and the persisted RunAborted event
    carries the trimmed reason.

Both paths run in the same module to share the upstream-chain
seeding pattern with `test_start_run_handler_postgres.py`. Each
test uses a distinct run_id (different aggregate stream) so they
don't interfere even if the test DB is shared.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features import (
    add_asset_family,
    define_family,
    register_asset,
)
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunStatus, load_run
from cora.run.features import abort_run, complete_run, start_run
from cora.run.features.abort_run import AbortRun
from cora.run.features.complete_run import CompleteRun
from cora.run.features.start_run import StartRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d26c")


def _build_deps_with_ids(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _seed_chain_and_start_run(
    deps: Kernel,
    *,
    asset_id: UUID,
    cap_id: UUID,
    method_id: UUID,
    practice_id: UUID,
    site_id: UUID,
    subject_id: UUID,
    plan_id: UUID,
    run_id: UUID,
) -> None:
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
    returned_id = await start_run.bind(deps)(
        StartRun(
            name="32-ID FlyScan morning session",
            plan_id=plan_id,
            subject_id=subject_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == run_id


@pytest.mark.integration
async def test_complete_run_persists_and_round_trips_to_completed_state(
    db_pool: asyncpg.Pool,
) -> None:
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-00000064aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000064ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000064ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000064ab03")
    method_id = UUID("01900000-0000-7000-8000-00000064ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000064ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000064ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000064ad02")
    site_id = UUID("01900000-0000-7000-8000-00000064ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000064af01")
    plan_event_id = UUID("01900000-0000-7000-8000-00000064af02")
    subject_id = UUID("01900000-0000-7000-8000-00000064b001")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000064b002")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000064b003")
    run_id = UUID("01900000-0000-7000-8000-00000064b101")
    run_started_event_id = UUID("01900000-0000-7000-8000-00000064b102")
    run_completed_event_id = UUID("01900000-0000-7000-8000-00000064b103")

    deps = _build_deps_with_ids(
        db_pool,
        [
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
            run_id,
            run_started_event_id,
            run_completed_event_id,
        ],
    )

    await _seed_chain_and_start_run(
        deps,
        asset_id=asset_id,
        cap_id=cap_id,
        method_id=method_id,
        practice_id=practice_id,
        site_id=site_id,
        subject_id=subject_id,
        plan_id=plan_id,
        run_id=run_id,
    )

    await complete_run.bind(deps)(
        CompleteRun(run_id=run_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, stream_version = await deps.event_store.load("Run", run_id)
    assert stream_version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunCompleted"]
    completed = events[1]
    assert completed.event_id == run_completed_event_id
    assert completed.metadata == {"command": "CompleteRun"}
    assert completed.payload == {
        "run_id": str(run_id),
        "occurred_at": _NOW.isoformat(),
    }

    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.subject_id == subject_id
    assert state.status is RunStatus.COMPLETED


@pytest.mark.integration
async def test_abort_run_persists_with_trimmed_reason_and_round_trips_to_aborted_state(
    db_pool: asyncpg.Pool,
) -> None:
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-00000065aa02")
    asset_id = UUID("01900000-0000-7000-8000-00000065ab01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000065ab02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000065ab03")
    method_id = UUID("01900000-0000-7000-8000-00000065ac01")
    method_event_id = UUID("01900000-0000-7000-8000-00000065ac02")
    practice_id = UUID("01900000-0000-7000-8000-00000065ad01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000065ad02")
    site_id = UUID("01900000-0000-7000-8000-00000065ae01")
    plan_id = UUID("01900000-0000-7000-8000-00000065af01")
    plan_event_id = UUID("01900000-0000-7000-8000-00000065af02")
    subject_id = UUID("01900000-0000-7000-8000-00000065b001")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000065b002")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000065b003")
    run_id = UUID("01900000-0000-7000-8000-00000065b101")
    run_started_event_id = UUID("01900000-0000-7000-8000-00000065b102")
    run_aborted_event_id = UUID("01900000-0000-7000-8000-00000065b103")

    deps = _build_deps_with_ids(
        db_pool,
        [
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
            run_id,
            run_started_event_id,
            run_aborted_event_id,
        ],
    )

    await _seed_chain_and_start_run(
        deps,
        asset_id=asset_id,
        cap_id=cap_id,
        method_id=method_id,
        practice_id=practice_id,
        site_id=site_id,
        subject_id=subject_id,
        plan_id=plan_id,
        run_id=run_id,
    )

    await abort_run.bind(deps)(
        AbortRun(run_id=run_id, reason="  detector overheating  "),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, stream_version = await deps.event_store.load("Run", run_id)
    assert stream_version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunAborted"]
    aborted = events[1]
    assert aborted.event_id == run_aborted_event_id
    assert aborted.metadata == {"command": "AbortRun"}
    assert aborted.payload == {
        "run_id": str(run_id),
        "reason": "detector overheating",
        # when AbortRun.decided_by_decision_id was not provided;
        # forward-compat via `payload.get("decided_by_decision_id")`.
        "decided_by_decision_id": None,
        "occurred_at": _NOW.isoformat(),
    }

    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.subject_id == subject_id
    assert state.status is RunStatus.ABORTED

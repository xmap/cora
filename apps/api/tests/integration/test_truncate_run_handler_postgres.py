"""End-to-end integration test: truncate_run against real Postgres.

Round-trip the partial-data terminal: full upstream chain + start +
truncate + load_run returns the Truncated state and the persisted
RunTruncated event carries:
  - the trimmed reason
  - interrupted_at preserved through jsonb round-trip (datetime,
    not just stringified bytes)
  - occurred_at distinct from interrupted_at (the two timestamps
    stay separate in the payload, matching the operator-supplied
    semantics: occurred_at = when truncation was processed,
    interrupted_at = operator's best guess at the actual
    interruption)

Mirrors the shape of `test_run_transitions_handler_postgres.py`'s
abort_run case (typed payload field, not just a string).
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
from cora.recipe.aggregates.method import ExecutionPattern
from cora.recipe.features import (
    define_method,
    define_plan,
    define_practice,
)
from cora.recipe.features.define_method import DefineMethod
from cora.recipe.features.define_plan import DefinePlan
from cora.recipe.features.define_practice import DefinePractice
from cora.run.aggregates.run import RunStatus, load_run
from cora.run.features import start_run, truncate_run
from cora.run.features.start_run import StartRun
from cora.run.features.truncate_run import TruncateRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_INTERRUPTED_AT = datetime(2026, 5, 9, 3, 14, 7, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d64c")


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
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="XRF Fly Scan",
            needed_family_ids=frozenset({cap_id}),
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
async def test_truncate_run_persists_with_interrupted_at_and_round_trips_to_truncated_state(
    db_pool: asyncpg.Pool,
) -> None:
    """End-to-end: truncate emits RunTruncated; payload preserves
    trimmed reason + interrupted_at; load_run returns the
    Truncated state."""
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-00000067cc02")
    asset_id = UUID("01900000-0000-7000-8000-00000067cd01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000067cd02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000067cd03")
    method_id = UUID("01900000-0000-7000-8000-00000067ce01")
    method_event_id = UUID("01900000-0000-7000-8000-00000067ce02")
    practice_id = UUID("01900000-0000-7000-8000-00000067cf01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000067cf02")
    site_id = UUID("01900000-0000-7000-8000-00000067d001")
    plan_id = UUID("01900000-0000-7000-8000-00000067d101")
    plan_event_id = UUID("01900000-0000-7000-8000-00000067d102")
    subject_id = UUID("01900000-0000-7000-8000-00000067d201")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000067d202")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000067d203")
    run_id = UUID("01900000-0000-7000-8000-00000067d301")
    run_started_event_id = UUID("01900000-0000-7000-8000-00000067d302")
    run_truncated_event_id = UUID("01900000-0000-7000-8000-00000067d303")

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
            run_truncated_event_id,
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

    await truncate_run.bind(deps)(
        TruncateRun(
            run_id=run_id,
            reason="  weekend power loss; abandoned at projection 487 of 1500  ",
            interrupted_at=_INTERRUPTED_AT,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, stream_version = await deps.event_store.load("Run", run_id)
    assert stream_version == 2
    assert [e.event_type for e in events] == ["RunStarted", "RunTruncated"]
    truncated = events[1]
    assert truncated.event_id == run_truncated_event_id
    assert truncated.metadata == {"command": "TruncateRun"}
    assert truncated.payload == {
        "run_id": str(run_id),
        "reason": "weekend power loss; abandoned at projection 487 of 1500",
        "interrupted_at": _INTERRUPTED_AT.isoformat(),
        "occurred_at": _NOW.isoformat(),
    }
    # The two timestamps stay distinct through jsonb (operator-
    # supplied interrupted_at on Saturday, system-recorded
    # occurred_at on Monday in our scenario).
    assert truncated.payload["interrupted_at"] != truncated.payload["occurred_at"]

    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.id == run_id
    assert state.plan_id == plan_id
    assert state.subject_id == subject_id
    assert state.status is RunStatus.TRUNCATED


@pytest.mark.integration
async def test_truncate_run_persists_null_interrupted_at_as_null(
    db_pool: asyncpg.Pool,
) -> None:
    """Operator-unknown interruption time round-trips as null
    through jsonb (not the string \"None\" or missing key)."""
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-00000068cc02")
    asset_id = UUID("01900000-0000-7000-8000-00000068cd01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-00000068cd02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-00000068cd03")
    method_id = UUID("01900000-0000-7000-8000-00000068ce01")
    method_event_id = UUID("01900000-0000-7000-8000-00000068ce02")
    practice_id = UUID("01900000-0000-7000-8000-00000068cf01")
    practice_event_id = UUID("01900000-0000-7000-8000-00000068cf02")
    site_id = UUID("01900000-0000-7000-8000-00000068d001")
    plan_id = UUID("01900000-0000-7000-8000-00000068d101")
    plan_event_id = UUID("01900000-0000-7000-8000-00000068d102")
    subject_id = UUID("01900000-0000-7000-8000-00000068d201")
    subject_register_event_id = UUID("01900000-0000-7000-8000-00000068d202")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-00000068d203")
    run_id = UUID("01900000-0000-7000-8000-00000068d301")
    run_started_event_id = UUID("01900000-0000-7000-8000-00000068d302")
    run_truncated_event_id = UUID("01900000-0000-7000-8000-00000068d303")

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
            run_truncated_event_id,
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

    await truncate_run.bind(deps)(
        TruncateRun(
            run_id=run_id,
            reason="found dangling Run; interruption time unknown",
            interrupted_at=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, _ = await deps.event_store.load("Run", run_id)
    truncated = events[1]
    assert truncated.payload["interrupted_at"] is None

    # Round-trip through fold preserves None (typed datetime|None,
    # not stringified).
    state = await load_run(deps.event_store, run_id)
    assert state is not None
    assert state.status is RunStatus.TRUNCATED

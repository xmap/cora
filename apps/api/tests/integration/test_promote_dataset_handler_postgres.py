"""End-to-end integration test: promote_dataset against real Postgres.

Standalone-upload Dataset (no producing_run, no derived_from): the
simplest end-to-end path that exercises promote_dataset's full
round-trip through the PG event store. Verifies:

  - DatasetPromoted event lands in the stream
  - load_dataset folds back with intent == Production
  - Re-promote raises DatasetAlreadyPromotedError (strict-not-idempotent
    over a real PG round-trip, not just the in-memory store)
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetAlreadyPromotedError,
    Intent,
    load_dataset,
)
from cora.data.features import promote_dataset, register_dataset
from cora.data.features.promote_dataset import PromoteDataset
from cora.data.features.register_dataset import RegisterDataset
from cora.infrastructure.kernel import Kernel
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d552")


def _build_deps(db_pool: asyncpg.Pool, ids: list[UUID]) -> Kernel:
    return build_postgres_deps(db_pool, now=_NOW, ids=ids)


async def _register_standalone_dataset(deps: Kernel) -> UUID:
    """Register a standalone-upload Dataset (no producing_run, no
    derived_from)."""
    return await register_dataset.bind(deps)(
        RegisterDataset(
            name="standalone-upload",
            uri="s3://bucket/key",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=0,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            producing_run_id=None,
            subject_id=None,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_promote_dataset_round_trips_event_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Full end-to-end: register a standalone Dataset, promote it,
    fold-on-read returns Intent.PRODUCTION."""
    deps = _build_deps(db_pool, [uuid4(), uuid4(), uuid4()])  # register + promote event ids

    dataset_id = await _register_standalone_dataset(deps)

    # Verify intent defaults to Trial after registration.
    after_register = await load_dataset(deps.event_store, dataset_id)
    assert after_register is not None
    assert after_register.intent is Intent.TRIAL

    # Promote it.
    await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=dataset_id, reason="passed peer review"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Verify intent flipped to Production via real PG round-trip.
    after_promote = await load_dataset(deps.event_store, dataset_id)
    assert after_promote is not None
    assert after_promote.intent is Intent.PRODUCTION


@pytest.mark.integration
async def test_re_promote_raises_already_promoted_against_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    """Strict-not-idempotent enforced over real PG round-trip."""
    deps = _build_deps(db_pool, [uuid4(), uuid4(), uuid4()])

    dataset_id = await _register_standalone_dataset(deps)

    # First promote succeeds.
    await promote_dataset.bind(deps)(
        PromoteDataset(dataset_id=dataset_id, reason="passed review"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Second promote raises.
    with pytest.raises(DatasetAlreadyPromotedError):
        await promote_dataset.bind(deps)(
            PromoteDataset(dataset_id=dataset_id, reason="trying again"),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_register_dataset_persists_producing_run_end_state_in_payload(
    db_pool: asyncpg.Pool,
) -> None:
    """Pin: the producing_run_end_state captured at register-time
    actually persists into the DatasetRegistered event's jsonb payload
    and survives a real PG round-trip (no silent drop, no field
    rename in storage). This is the audit trail that powers the
    promote_dataset Run-must-be-Completed guard."""
    from cora.equipment.aggregates.asset import AssetTier
    from cora.equipment.features import (
        add_asset_family,
        define_family,
        register_asset,
    )
    from cora.equipment.features.add_asset_family import AddAssetFamily
    from cora.equipment.features.define_family import DefineFamily
    from cora.equipment.features.register_asset import RegisterAsset
    from cora.recipe.aggregates.method import ExecutionPattern
    from cora.recipe.features import define_method, define_plan, define_practice
    from cora.recipe.features.define_method import DefineMethod
    from cora.recipe.features.define_plan import DefinePlan
    from cora.recipe.features.define_practice import DefinePractice
    from cora.run.features import abort_run, start_run
    from cora.run.features.abort_run import AbortRun
    from cora.run.features.start_run import StartRun
    from cora.subject.features import mount_subject, register_subject
    from cora.subject.features.mount_subject import MountSubject
    from cora.subject.features.register_subject import RegisterSubject
    from tests.unit.subject._helpers import seed_active_asset

    # Generous id pool: full upstream chain + Run + abort + Dataset.
    deps = _build_deps(db_pool, [uuid4() for _ in range(20)])

    # Set up: Family → Method → Practice → Asset → Plan → Subject → Run
    cap_id = await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await seed_capability_postgres(deps.event_store, _CAPABILITY_ID)
    method_id = await define_method.bind(deps)(
        DefineMethod(
            execution_pattern=ExecutionPattern.BATCH,
            capability_id=_CAPABILITY_ID,
            name="M",
            needed_family_ids=frozenset({cap_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    practice_id = await define_practice.bind(deps)(
        DefinePractice(name="P", method_id=method_id, site_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(name="A", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=cap_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    plan_id = await define_plan.bind(deps)(
        DefinePlan(name="Plan", practice_id=practice_id, asset_ids=frozenset({asset_id})),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    subject_id = await register_subject.bind(deps)(
        RegisterSubject(name="Sample"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    mount_asset_id = await seed_active_asset(
        deps.event_store, now=_NOW, correlation_id=_CORRELATION_ID
    )
    await mount_subject.bind(deps)(
        MountSubject(subject_id=subject_id, asset_id=mount_asset_id, reason="test"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    run_id = await start_run.bind(deps)(
        StartRun(
            name="Run",
            plan_id=plan_id,
            subject_id=subject_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # Drive the Run to Aborted so the captured end_state is non-trivial.
    await abort_run.bind(deps)(
        AbortRun(run_id=run_id, reason="simulated abort for test"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Register the Dataset against the Aborted Run.
    dataset_id = await register_dataset.bind(deps)(
        RegisterDataset(
            name="post-abort dataset",
            uri="s3://bucket/post-abort.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=42,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            producing_run_id=run_id,
            subject_id=subject_id,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Inspect the persisted DatasetRegistered event's payload directly.
    stored_events, _ = await deps.event_store.load(stream_type="Dataset", stream_id=dataset_id)
    assert len(stored_events) == 1
    payload = stored_events[0].payload
    # The producing_run_end_state is the captured Run terminal state
    # at the moment of dataset registration. Run was aborted before
    # the dataset registered, so we expect "Aborted" (not "Running").
    assert payload["producing_run_end_state"] == "Aborted"
    # Intent defaults to Trial on registration.
    assert payload["intent"] == "Trial"

"""End-to-end integration test: register_dataset against real Postgres.

7c locks the cross-track eventual-consistency story end-to-end.
Sets up the full upstream chain (Family → Asset → Method →
Practice → Plan → Subject → Run), registers a raw Dataset against
the Run + Subject, registers a derived Dataset against the raw
one + same Subject + same Run, and verifies:

  - Both Datasets land with the right cross-aggregate refs in the
    persisted event payload (jsonb round-trip preserves UUID list
    + sorted conforms_to).
  - load_dataset folds back to Dataset domain objects with the
    references walkable.
  - The 7b lineage-into-Discarded guard fires against real
    Postgres: discard the raw Dataset, then attempt to register
    a third Dataset with the discarded one as a derived_from
    source -> DerivedFromDatasetsDiscardedError.

Mirrors the shape of `test_run_transitions_handler_postgres.py`
(typed payload fields, full chain seeding).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.data.aggregates.dataset import (
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DatasetStatus,
    DerivedFromDatasetsDiscardedError,
    load_dataset,
)
from cora.data.features import discard_dataset, register_dataset
from cora.data.features.discard_dataset import DiscardDataset
from cora.data.features.register_dataset import RegisterDataset
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
from cora.run.features import start_run
from cora.run.features.start_run import StartRun
from cora.subject.features import mount_subject, register_subject
from cora.subject.features.mount_subject import MountSubject
from cora.subject.features.register_subject import RegisterSubject
from tests.integration._helpers import build_postgres_deps, seed_capability_postgres
from tests.unit.subject._helpers import seed_active_asset

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPABILITY_ID = UUID("01900000-0000-7000-8000-000000c0d2cf")


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
    raid: str | None = None,
) -> None:
    await define_family.bind(deps)(
        DefineFamily(name="FlyMotion", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await register_asset.bind(deps)(
        RegisterAsset(
            name="EigerDetector",
            tier=AssetTier.UNIT,
            parent_id=None,
            facility_code="cora",
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
            raid=raid,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned_id == run_id


@pytest.mark.integration
async def test_register_dataset_against_run_subject_and_lineage_round_trip(
    db_pool: asyncpg.Pool,
) -> None:
    """Full upstream chain → Run → raw Dataset → derived Dataset →
    fold both → discard raw → derived-from-Discarded guard fires."""
    cap_id = family_stream_id(FamilyName("FlyMotion"))
    cap_event_id = UUID("01900000-0000-7000-8000-000000077a02")
    asset_id = UUID("01900000-0000-7000-8000-000000077b01")
    asset_register_event_id = UUID("01900000-0000-7000-8000-000000077b02")
    asset_addcap_event_id = UUID("01900000-0000-7000-8000-000000077b03")
    method_id = UUID("01900000-0000-7000-8000-000000077c01")
    method_event_id = UUID("01900000-0000-7000-8000-000000077c02")
    practice_id = UUID("01900000-0000-7000-8000-000000077d01")
    practice_event_id = UUID("01900000-0000-7000-8000-000000077d02")
    site_id = UUID("01900000-0000-7000-8000-000000077e01")
    plan_id = UUID("01900000-0000-7000-8000-000000077f01")
    plan_event_id = UUID("01900000-0000-7000-8000-000000077f02")
    subject_id = UUID("01900000-0000-7000-8000-000000078000")
    subject_register_event_id = UUID("01900000-0000-7000-8000-000000078001")
    subject_mount_event_id = UUID("01900000-0000-7000-8000-000000078002")
    run_id = UUID("01900000-0000-7000-8000-000000078101")
    run_started_event_id = UUID("01900000-0000-7000-8000-000000078102")
    raw_dataset_id = UUID("01900000-0000-7000-8000-000000078201")
    raw_dataset_event_id = UUID("01900000-0000-7000-8000-000000078202")
    derived_dataset_id = UUID("01900000-0000-7000-8000-000000078301")
    derived_dataset_event_id = UUID("01900000-0000-7000-8000-000000078302")
    discard_event_id = UUID("01900000-0000-7000-8000-000000078401")
    third_dataset_id = UUID("01900000-0000-7000-8000-000000078501")
    third_dataset_event_id = UUID("01900000-0000-7000-8000-000000078502")

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
            raw_dataset_id,
            raw_dataset_event_id,
            derived_dataset_id,
            derived_dataset_event_id,
            discard_event_id,
            third_dataset_id,
            third_dataset_event_id,
        ],
    )

    raid_value = "https://raid.org/10.7935/cora-7c-integration"
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
        raid=raid_value,
    )

    # 7d round-trip check: raid persists through PostgresEventStore
    # jsonb + load_run fold, even though no Data BC code reads it.
    from cora.run.aggregates.run import load_run

    run_state = await load_run(deps.event_store, run_id)
    assert run_state is not None
    assert run_state.raid == raid_value

    # Register raw Dataset against the Run + Subject.
    raw_id = await register_dataset.bind(deps)(
        RegisterDataset(
            name="raw projections",
            uri="s3://aps-32id/runs/abc/raw.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=10_000_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset({"https://manual.nexusformat.org/"}),
            producing_run_id=run_id,
            subject_id=subject_id,
            derived_from=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert raw_id == raw_dataset_id

    # Register derived Dataset using the raw one as lineage source.
    derived_id = await register_dataset.bind(deps)(
        RegisterDataset(
            name="reconstruction",
            uri="s3://aps-32id/runs/abc/recon.h5",
            checksum_algorithm="sha256",
            checksum_value="b" * DATASET_CHECKSUM_SHA256_HEX_LENGTH,
            byte_size=20_000_000,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
            producing_run_id=run_id,
            subject_id=subject_id,
            derived_from=frozenset({raw_id}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert derived_id == derived_dataset_id

    # Fold both Datasets back through Postgres + verify cross-track refs.
    raw = await load_dataset(deps.event_store, raw_id)
    assert raw is not None
    assert raw.id == raw_id
    assert raw.producing_run_id == run_id
    assert raw.subject_id == subject_id
    assert raw.derived_from == frozenset()
    assert raw.encoding.conforms_to == frozenset({"https://manual.nexusformat.org/"})
    assert raw.status is DatasetStatus.REGISTERED

    derived = await load_dataset(deps.event_store, derived_id)
    assert derived is not None
    assert derived.id == derived_id
    assert derived.producing_run_id == run_id
    assert derived.subject_id == subject_id
    assert derived.derived_from == frozenset({raw_id})
    assert derived.status is DatasetStatus.REGISTERED

    # Verify the persisted event payload preserves the cross-track refs as
    # canonical strings (jsonb-friendly, sorted set semantics).
    raw_events, _ = await deps.event_store.load("Dataset", raw_id)
    assert len(raw_events) == 1
    assert raw_events[0].payload["producing_run_id"] == str(run_id)
    assert raw_events[0].payload["subject_id"] == str(subject_id)
    assert raw_events[0].payload["derived_from"] == []
    assert raw_events[0].payload["encoding"]["conforms_to"] == ["https://manual.nexusformat.org/"]

    # (the entire API surface without used_calibration_ids) get an empty list
    # on the persisted payload. Locks the additive-state forward-compat
    # contract: any regression that drops the field-default would
    # break legacy from_stored fold + read-path consumers without the field.
    assert raw_events[0].payload["used_calibration_ids"] == []

    derived_events, _ = await deps.event_store.load("Dataset", derived_id)
    assert len(derived_events) == 1
    assert derived_events[0].payload["derived_from"] == [str(raw_id)]

    assert derived_events[0].payload["used_calibration_ids"] == []

    # Discard the raw Dataset (GDPR-shaped).
    await discard_dataset.bind(deps)(
        DiscardDataset(dataset_id=raw_id, reason="GDPR Article 17 erasure request"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    raw_after_discard = await load_dataset(deps.event_store, raw_id)
    assert raw_after_discard is not None
    assert raw_after_discard.status is DatasetStatus.DISCARDED

    # 7b lineage-into-Discarded guard against real Postgres: register
    # a third Dataset with the discarded raw as a derived_from source.
    with pytest.raises(DerivedFromDatasetsDiscardedError) as exc_info:
        await register_dataset.bind(deps)(
            RegisterDataset(
                name="re-derived attempt",
                uri="s3://aps-32id/runs/abc/redo.h5",
                checksum_algorithm="sha256",
                checksum_value="c" * DATASET_CHECKSUM_SHA256_HEX_LENGTH,
                byte_size=30_000_000,
                media_type="application/x-hdf5",
                conforms_to=frozenset(),
                producing_run_id=None,
                subject_id=None,
                derived_from=frozenset({raw_id}),
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.discarded_ids == [raw_id]

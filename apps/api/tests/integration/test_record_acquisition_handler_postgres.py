"""End-to-end integration test: record_acquisition against real Postgres.

Seeds a Capturing-affordance Family + an Asset bound to it + a
Dataset, drains the equipment + data projections so the
PostgresAssetLookup JOIN over proj_equipment_asset_family_membership
-> proj_equipment_family_summary resolves the affordance set, then:

  - records an Acquisition (happy path) and verifies the persisted
    event payload + load_acquisition fold + projection row.
  - rejects an Asset whose Family lacks Capturing ->
    AcquisitionCannotRecordWithoutCapturingError.
  - rejects an unknown Dataset -> DatasetNotFoundError.
  - rejects an unknown Asset -> AcquisitionAssetNotFoundError.

Mirrors test_register_dataset_handler_postgres.py (full chain seeding
through the real adapters).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.data.aggregates.acquisition import (
    AcquisitionAssetNotFoundError,
    AcquisitionCannotRecordWithoutCapturingError,
    AcquisitionStatus,
    load_acquisition,
)
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH, DatasetNotFoundError
from cora.data.features import record_acquisition, register_dataset
from cora.data.features.record_acquisition import RecordAcquisition
from cora.data.features.register_dataset import RegisterDataset
from cora.equipment.adapters import PostgresAssetLookup
from cora.equipment.aggregates.asset import AssetTier
from cora.equipment.aggregates.family import Affordance
from cora.equipment.features import add_asset_family, define_family, register_asset
from cora.equipment.features.add_asset_family import AddAssetFamily
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.register_asset import RegisterAsset
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests.integration._helpers import build_postgres_deps

_GOOD_SHA256 = "a" * DATASET_CHECKSUM_SHA256_HEX_LENGTH
_NOW = datetime(2026, 6, 11, 12, 0, 0, tzinfo=UTC)
_CAPTURED_AT = datetime(2026, 6, 10, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CAPTURING = frozenset({Affordance.CAPTURING})
_IMAGEABLE = frozenset({Affordance.IMAGEABLE})


def _deps(db_pool: asyncpg.Pool) -> Kernel:
    """Kernel wired with the real PostgresAssetLookup (the default is an
    empty InMemoryAssetLookup, which would never resolve the seeded
    Asset's Capturing affordance)."""
    return build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(16)],
        asset_lookup=PostgresAssetLookup(db_pool),
    )


async def _drain(db_pool: asyncpg.Pool) -> None:
    from cora.equipment._projections import register_equipment_projections

    registry = ProjectionRegistry()
    register_equipment_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)


async def _seed_capturing_asset(deps: Kernel, *, family_affordances: frozenset[Affordance]) -> UUID:
    family_id = await define_family.bind(deps)(
        DefineFamily(name="TomographyDetector", affordances=family_affordances),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    asset_id = await register_asset.bind(deps)(
        RegisterAsset(
            name="OryxDetector", tier=AssetTier.UNIT, parent_id=None, facility_code="cora"
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await add_asset_family.bind(deps)(
        AddAssetFamily(asset_id=asset_id, family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return asset_id


async def _seed_dataset(deps: Kernel) -> UUID:
    return await register_dataset.bind(deps)(
        RegisterDataset(
            name="recon.h5",
            uri="s3://aps-2bm/recon.h5",
            checksum_algorithm="sha256",
            checksum_value=_GOOD_SHA256,
            byte_size=1024,
            media_type="application/x-hdf5",
            conforms_to=frozenset(),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_record_acquisition_happy_path_round_trip(db_pool: asyncpg.Pool) -> None:
    """Capturing-bearing Asset + Dataset -> Acquisition stream + projection row."""
    deps = _deps(db_pool)
    asset_id = await _seed_capturing_asset(deps, family_affordances=_CAPTURING)
    dataset_id = await _seed_dataset(deps)
    await _drain(db_pool)

    acquisition_id = await record_acquisition.bind(deps)(
        RecordAcquisition(
            dataset_id=dataset_id,
            producing_asset_id=asset_id,
            captured_at=_CAPTURED_AT,
            settings={"exposure_ms": 200},
            evidence={"frames": 1801},
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Fold the Acquisition stream back through Postgres.
    acq = await load_acquisition(deps.event_store, acquisition_id)
    assert acq is not None
    assert acq.id == acquisition_id
    assert acq.dataset_id == dataset_id
    assert acq.producing_asset_id == asset_id
    assert acq.producing_run_id is None
    assert acq.captured_at == _CAPTURED_AT
    assert acq.recorded_at == _NOW
    assert acq.settings == {"exposure_ms": 200}
    assert acq.evidence == {"frames": 1801}
    assert acq.status is AcquisitionStatus.RECORDED

    # Persisted event payload preserves dual-time + bindings.
    events, version = await deps.event_store.load("Acquisition", acquisition_id)
    assert version == 1
    assert events[0].payload["captured_at"] == _CAPTURED_AT.isoformat()
    assert events[0].payload["occurred_at"] == _NOW.isoformat()
    assert events[0].payload["producing_run_id"] is None

    # Projection row lands after drain.
    registry = ProjectionRegistry()
    from cora.data._projections import register_data_projections

    register_data_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=2.0)
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT acquisition_id, dataset_id, producing_asset_id, captured_at, "
            "recorded_at, status, settings, evidence "
            "FROM proj_data_acquisition_summary WHERE acquisition_id = $1",
            acquisition_id,
        )
    assert row is not None
    assert row["dataset_id"] == dataset_id
    assert row["producing_asset_id"] == asset_id
    assert row["captured_at"] == _CAPTURED_AT
    assert row["recorded_at"] == _NOW
    assert row["status"] == "Recorded"


@pytest.mark.integration
async def test_record_acquisition_rejects_missing_capturing_affordance(
    db_pool: asyncpg.Pool,
) -> None:
    """An Asset whose Family declares Imageable (not Capturing) is rejected."""
    deps = _deps(db_pool)
    asset_id = await _seed_capturing_asset(deps, family_affordances=_IMAGEABLE)
    dataset_id = await _seed_dataset(deps)
    await _drain(db_pool)

    with pytest.raises(AcquisitionCannotRecordWithoutCapturingError) as exc:
        await record_acquisition.bind(deps)(
            RecordAcquisition(
                dataset_id=dataset_id,
                producing_asset_id=asset_id,
                captured_at=_CAPTURED_AT,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc.value.asset_id == asset_id


@pytest.mark.integration
async def test_record_acquisition_rejects_unknown_dataset(db_pool: asyncpg.Pool) -> None:
    deps = _deps(db_pool)
    asset_id = await _seed_capturing_asset(deps, family_affordances=_CAPTURING)
    await _drain(db_pool)

    with pytest.raises(DatasetNotFoundError):
        await record_acquisition.bind(deps)(
            RecordAcquisition(
                dataset_id=uuid4(),
                producing_asset_id=asset_id,
                captured_at=_CAPTURED_AT,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


@pytest.mark.integration
async def test_record_acquisition_rejects_unknown_asset(db_pool: asyncpg.Pool) -> None:
    deps = _deps(db_pool)
    dataset_id = await _seed_dataset(deps)
    await _drain(db_pool)

    with pytest.raises(AcquisitionAssetNotFoundError):
        await record_acquisition.bind(deps)(
            RecordAcquisition(
                dataset_id=dataset_id,
                producing_asset_id=uuid4(),
                captured_at=_CAPTURED_AT,
            ),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )

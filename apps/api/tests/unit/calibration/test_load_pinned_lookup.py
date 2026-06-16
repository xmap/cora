"""Unit tests for `load_pinned_lookup`, the cross-BC lookup-load helper.

`load_pinned_lookup` is what a LookupTable partition-rule evaluator calls
to turn a pinned `(calibration_id, revision_id)` into the `(independent,
dependent)` points it interpolates. It owns all Calibration-payload
knowledge so the consuming kernel stays decoupled. These tests pin its
branches: a continuous energy curve returns its points, a discrete index
table returns its (slot-index, position) points, a dangling pin (missing
calibration or missing revision) returns None, and a scalar-valued
calibration raises rather than KeyError on a missing `points` key.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    AssertedSource,
    CalibrationNotLookupValuedError,
    CalibrationStatus,
)
from cora.calibration.aggregates.calibration.read import load_pinned_lookup
from cora.calibration.features.append_calibration_revision import AppendCalibrationRevision
from cora.calibration.features.append_calibration_revision import (
    bind as bind_append_calibration_revision,
)
from cora.calibration.features.define_calibration import DefineCalibration
from cora.calibration.features.define_calibration import bind as bind_define_calibration
from cora.calibration.quantities import CalibrationQuantity
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.kernel import Kernel
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 6, 16, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_TARGET_ID = UUID("01900000-0000-7000-8000-00000000cc01")
_ACTOR = ActorId(_PRINCIPAL_ID)


def _deps(store: InMemoryEventStore) -> Kernel:
    return _build_deps_shared(ids=[uuid4() for _ in range(20)], now=_NOW, event_store=store)


async def _seed_energy_curve(store: InMemoryEventStore) -> tuple[UUID, UUID]:
    deps = _deps(store)
    cal_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=_TARGET_ID,
            quantity=CalibrationQuantity.ENERGY_POSITION_CURVE,
            operating_point={"axis_designation": "dmm_us_arm", "beam_mode": "mono"},
            description="curve under test",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rev_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=cal_id,
            value={
                "points": [
                    {"energy": 18.0, "position": 0.6},
                    {"energy": 25.0, "position": 0.9},
                ],
                "provisional": True,
            },
            status=CalibrationStatus.PROVISIONAL,
            source=AssertedSource(asserted_by=_ACTOR),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return cal_id, rev_id


@pytest.mark.unit
async def test_load_pinned_lookup_returns_points_for_curve_calibration() -> None:
    store = InMemoryEventStore()
    cal_id, rev_id = await _seed_energy_curve(store)
    curve = await load_pinned_lookup(store, cal_id, rev_id)
    assert curve == ((18.0, 0.6), (25.0, 0.9))


@pytest.mark.unit
async def test_load_pinned_lookup_returns_indexed_points_for_index_table() -> None:
    store = InMemoryEventStore()
    deps = _deps(store)
    cal_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=_TARGET_ID,
            quantity=CalibrationQuantity.INDEX_POSITION_TABLE,
            operating_point={"device_designation": "downstream_filter_paddle"},
            description="discrete foil table under test",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rev_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=cal_id,
            value={
                "points": [
                    {"name": "600 um Al", "position": 0.0},
                    {"name": "150 um Al", "position": 26.0},
                    {"name": "None", "position": 106.0},
                ],
                "position_unit": "mm",
            },
            status=CalibrationStatus.PROVISIONAL,
            source=AssertedSource(asserted_by=_ACTOR),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    # The slot index is the array order: (0, 0.0), (1, 26.0), (2, 106.0).
    points = await load_pinned_lookup(store, cal_id, rev_id)
    assert points == ((0.0, 0.0), (1.0, 26.0), (2.0, 106.0))


@pytest.mark.unit
async def test_load_pinned_lookup_returns_none_when_calibration_absent() -> None:
    store = InMemoryEventStore()
    curve = await load_pinned_lookup(store, uuid4(), uuid4())
    assert curve is None


@pytest.mark.unit
async def test_load_pinned_lookup_returns_none_when_revision_absent() -> None:
    store = InMemoryEventStore()
    cal_id, _rev_id = await _seed_energy_curve(store)
    curve = await load_pinned_lookup(store, cal_id, uuid4())
    assert curve is None


@pytest.mark.unit
async def test_load_pinned_lookup_raises_for_scalar_valued_calibration() -> None:
    store = InMemoryEventStore()
    deps = _deps(store)
    cal_id = await bind_define_calibration(deps)(
        DefineCalibration(
            target_id=_TARGET_ID,
            quantity=CalibrationQuantity.MAGNIFICATION,
            operating_point={"objective_designation": "5x", "energy": 25.0},
            description="scalar calibration, not a curve",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    rev_id = await bind_append_calibration_revision(deps)(
        AppendCalibrationRevision(
            calibration_id=cal_id,
            value={"magnification": 9.83},
            status=CalibrationStatus.PROVISIONAL,
            source=AssertedSource(asserted_by=_ACTOR),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    with pytest.raises(CalibrationNotLookupValuedError) as info:
        await load_pinned_lookup(store, cal_id, rev_id)
    assert info.value.quantity == CalibrationQuantity.MAGNIFICATION.value

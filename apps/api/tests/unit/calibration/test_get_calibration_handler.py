"""Application-handler tests for `get_calibration` query slice."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.calibration.aggregates.calibration import (
    CalibrationDefined,
    CalibrationStatus,
    event_type_name,
    to_payload,
)
from cora.calibration.errors import UnauthorizedError
from cora.calibration.features import get_calibration
from cora.calibration.features.get_calibration import GetCalibration
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event
from cora.shared.identity import ActorId
from tests.unit._helpers import build_deps as _build_deps_shared

_NOW = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
_CAL_ID = UUID("01900000-0000-7000-8000-000000ca3001")
_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-000000ca3002")
_SUBSYSTEM_ID = UUID("01900000-0000-7000-8000-000000ca3003")
_ACTOR_ID = ActorId(UUID("01900000-0000-7000-8000-000000ca3004"))
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


async def _seed(store: InMemoryEventStore) -> None:
    genesis = CalibrationDefined(
        calibration_id=_CAL_ID,
        target_id=_SUBSYSTEM_ID,
        quantity="rotation_center",
        operating_point={"energy": 25.0, "optics_config": "5x"},
        description="vessel-A pre-scan",
        defined_by=_ACTOR_ID,
        occurred_at=_NOW,
    )
    new_event = to_new_event(
        event_type=event_type_name(genesis),
        payload=to_payload(genesis),
        occurred_at=genesis.occurred_at,
        event_id=_GENESIS_EVENT_ID,
        command_name="DefineCalibration",
        correlation_id=_CORRELATION_ID,
        causation_id=None,
        principal_id=_ACTOR_ID,
    )
    await store.append(
        stream_type="Calibration",
        stream_id=_CAL_ID,
        expected_version=0,
        events=[new_event],
    )


@pytest.mark.unit
async def test_handler_returns_calibration_view_on_hit() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_calibration.bind(deps)
    view = await handler(
        GetCalibration(calibration_id=_CAL_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is not None
    assert view.calibration.id == _CAL_ID
    assert view.calibration.target_id == _SUBSYSTEM_ID
    assert view.calibration.quantity == "rotation_center"
    assert view.calibration.operating_point == {"energy": 25.0, "optics_config": "5x"}
    assert view.calibration.description == "vessel-A pre-scan"
    assert view.calibration.revisions == ()
    # No pool in this in-memory test, so projection-sourced timestamps
    # are absent. Pin the contract: the handler returns CalibrationView
    # with timestamps=None rather than failing.
    assert view.timestamps is None


@pytest.mark.unit
async def test_handler_returns_none_on_miss() -> None:
    store = InMemoryEventStore()
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store)
    handler = get_calibration.bind(deps)
    view = await handler(
        GetCalibration(calibration_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    store = InMemoryEventStore()
    await _seed(store)
    deps = _build_deps_shared(ids=[], now=_NOW, event_store=store, deny=True)
    handler = get_calibration.bind(deps)
    with pytest.raises(UnauthorizedError):
        await handler(
            GetCalibration(calibration_id=_CAL_ID),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )


# Silence the unused-import linter for the optional CalibrationStatus.
_ = CalibrationStatus

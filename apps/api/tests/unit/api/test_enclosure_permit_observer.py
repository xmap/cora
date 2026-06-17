"""Unit tests for the SecureM -> permit-status mapping (composition-root bridge).

The async multi-PV merge + disconnect behaviour of
`ControlPortEnclosureObserver` is exercised end-to-end by the A3 monitor-loop
integration test; here we pin the pure, deterministic mapping that decides
each observation's status.
"""

from datetime import UTC, datetime

import pytest

from cora.api._enclosure_permit_observer import permit_status_from_reading
from cora.operation.ports.control_port import Reading

_T = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _reading(value: object, quality: str = "Good") -> Reading:
    return Reading(value=value, kind="Scalar", quality=quality, sampled_at=_T)  # type: ignore[arg-type]


@pytest.mark.unit
def test_secure_maps_to_permitted() -> None:
    assert permit_status_from_reading(_reading(1)) == "Permitted"
    assert permit_status_from_reading(_reading(1.0)) == "Permitted"
    assert permit_status_from_reading(_reading("1")) == "Permitted"
    assert permit_status_from_reading(_reading(True)) == "Permitted"


@pytest.mark.unit
def test_insecure_maps_to_not_permitted() -> None:
    assert permit_status_from_reading(_reading(0)) == "NotPermitted"
    assert permit_status_from_reading(_reading("0")) == "NotPermitted"


@pytest.mark.unit
def test_non_good_quality_flattens_to_unknown() -> None:
    assert permit_status_from_reading(_reading(1, quality="Bad")) == "Unknown"
    assert permit_status_from_reading(_reading(0, quality="Uncertain")) == "Unknown"


@pytest.mark.unit
def test_unexpected_value_flattens_to_unknown() -> None:
    assert permit_status_from_reading(_reading(2)) == "Unknown"
    assert permit_status_from_reading(_reading(None)) == "Unknown"
    assert permit_status_from_reading(_reading("secure")) == "Unknown"

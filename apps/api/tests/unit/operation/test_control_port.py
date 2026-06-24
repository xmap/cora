"""Port-surface tests for `ControlPort`: Measurement immutability + exception attrs.

Locks the surface promises the production adapters (CaprotoControlPort,
EpicsCaControlPort, EpicsPvaControlPort, future TangoControlPort /
OpcUaControlPort) inherit. Behavioural tests for `InMemoryControlPort`
live in `test_in_memory_control_port.py`.
"""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from cora.operation.ports.control_port import (
    ControlAccessDeniedError,
    ControlNotConnectedError,
    ControlTimeoutError,
    ControlValueCoercionError,
    ControlWriteRejectedError,
    Measurement,
    NoAdapterForAddressError,
)


@pytest.mark.unit
def test_reading_is_frozen_dataclass() -> None:
    r = Measurement(
        value=1.5,
        kind="Scalar",
        quality="Good",
        produced_at=datetime(2026, 5, 27, tzinfo=UTC),
    )
    with pytest.raises(FrozenInstanceError):
        r.value = 2.0  # type: ignore[misc]


@pytest.mark.unit
def test_reading_defaults_quality_detail_to_empty_string() -> None:
    r = Measurement(
        value=1.5,
        kind="Scalar",
        quality="Good",
        produced_at=datetime(2026, 5, 27, tzinfo=UTC),
    )
    assert r.quality_detail == ""


@pytest.mark.unit
def test_reading_equality_by_field_tuple() -> None:
    ts = datetime(2026, 5, 27, tzinfo=UTC)
    a = Measurement(value=1.5, kind="Scalar", quality="Good", produced_at=ts)
    b = Measurement(value=1.5, kind="Scalar", quality="Good", produced_at=ts)
    assert a == b
    assert hash(a) == hash(b)


@pytest.mark.unit
def test_control_not_connected_error_carries_address() -> None:
    err = ControlNotConnectedError("2bm:rot:rbv")
    assert err.address == "2bm:rot:rbv"
    assert "2bm:rot:rbv" in str(err)


@pytest.mark.unit
def test_control_timeout_error_carries_address_and_timeout() -> None:
    err = ControlTimeoutError("2bm:rot:val", timeout_s=5.0)
    assert err.address == "2bm:rot:val"
    assert err.timeout_s == 5.0
    assert "5.0" in str(err)


@pytest.mark.unit
def test_control_write_rejected_error_carries_address_and_reason() -> None:
    err = ControlWriteRejectedError("2bm:rot:val", reason="read-only")
    assert err.address == "2bm:rot:val"
    assert err.reason == "read-only"
    assert "read-only" in str(err)


@pytest.mark.unit
def test_control_value_coercion_error_carries_address_raw_type_and_target_kind() -> None:
    err = ControlValueCoercionError("2bm:cam:image", raw_type="NTFancy", target_kind="Image")
    assert err.address == "2bm:cam:image"
    assert err.raw_type == "NTFancy"
    assert err.target_kind == "Image"


@pytest.mark.unit
def test_control_access_denied_error_carries_address() -> None:
    err = ControlAccessDeniedError("2bm:safety:shutter")
    assert err.address == "2bm:safety:shutter"


@pytest.mark.unit
def test_no_adapter_for_address_error_carries_address() -> None:
    err = NoAdapterForAddressError("unrouted:something")
    assert err.address == "unrouted:something"

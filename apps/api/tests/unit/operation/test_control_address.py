"""Unit tests for the typed `ControlAddress` sum + `parse_control_address`.

Covers the str->typed dispatch the `ControlPortRegistry` performs at
route-match time: each substrate parses into its variant, per-variant
syntax validation raises `MalformedControlAddressError`, and every variant
round-trips back to its original string via `str(...)` (so logging +
`Measurement.name` breadcrumbs stay stable across the typed boundary).
"""

from __future__ import annotations

import pytest

from cora.operation.ports.control_address import (
    EpicsPvAddress,
    InMemoryAddress,
    MalformedControlAddressError,
    TangoAttributeAddress,
    parse_control_address,
)


@pytest.mark.unit
def test_parse_epics_ca_returns_epics_pv_address() -> None:
    addr = parse_control_address("2bma:rot", "epics_ca")
    assert addr == EpicsPvAddress("2bma:rot")
    assert str(addr) == "2bma:rot"


@pytest.mark.unit
def test_parse_epics_pva_returns_epics_pv_address() -> None:
    """CA and PVA share the `EpicsPvAddress` variant (transport is a route decision)."""
    addr = parse_control_address("2bma:cam1:image", "epics_pva")
    assert addr == EpicsPvAddress("2bma:cam1:image")


@pytest.mark.unit
def test_parse_tango_splits_trl_into_device_and_attribute() -> None:
    addr = parse_control_address("id19/bsh/1/state", "tango")
    assert addr == TangoAttributeAddress(device="id19/bsh/1", attribute="state")
    assert str(addr) == "id19/bsh/1/state"


@pytest.mark.unit
def test_parse_in_memory_returns_in_memory_address() -> None:
    addr = parse_control_address("sim:rot", "in_memory")
    assert addr == InMemoryAddress("sim:rot")
    assert str(addr) == "sim:rot"


@pytest.mark.unit
def test_epics_pv_address_rejects_empty_pv() -> None:
    with pytest.raises(MalformedControlAddressError) as exc_info:
        parse_control_address("", "epics_ca")
    assert exc_info.value.substrate == "epics_ca"


@pytest.mark.unit
def test_tango_address_without_attribute_segment_is_malformed() -> None:
    """A TRL with no `/` has no attribute segment and cannot route (was the
    adapter's `_split_trl` guard; now enforced once at the registry boundary)."""
    with pytest.raises(MalformedControlAddressError) as exc_info:
        parse_control_address("nodelimiter", "tango")
    assert exc_info.value.raw == "nodelimiter"
    assert exc_info.value.substrate == "tango"


@pytest.mark.unit
def test_tango_address_trailing_slash_is_malformed() -> None:
    with pytest.raises(MalformedControlAddressError):
        parse_control_address("id19/bsh/1/", "tango")


@pytest.mark.unit
def test_in_memory_address_rejects_empty() -> None:
    with pytest.raises(MalformedControlAddressError):
        parse_control_address("", "in_memory")


@pytest.mark.unit
def test_control_address_variants_are_frozen() -> None:
    addr = EpicsPvAddress("2bma:rot")
    with pytest.raises(AttributeError):
        addr.pv = "other"  # pyright: ignore[reportAttributeAccessIssue]

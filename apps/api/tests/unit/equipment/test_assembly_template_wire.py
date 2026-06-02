"""Unit tests for the TemplateWire value object."""

import pytest

from cora.equipment.aggregates.assembly import (
    WIRE_PORT_NAME_MAX_LENGTH,
    InvalidWireSpecError,
    TemplateWire,
)


@pytest.mark.unit
def test_template_wire_minimal_construction() -> None:
    wire = TemplateWire(
        source_slot_name="trigger_source",
        source_port_name="trigger_out",
        target_slot_name="camera",
        target_port_name="trigger_in",
    )
    assert wire.source_slot_name == "trigger_source"
    assert wire.source_port_name == "trigger_out"
    assert wire.target_slot_name == "camera"
    assert wire.target_port_name == "trigger_in"


@pytest.mark.unit
def test_template_wire_trims_all_four_fields() -> None:
    wire = TemplateWire(
        source_slot_name="  src_slot  ",
        source_port_name="  src_port  ",
        target_slot_name="  tgt_slot  ",
        target_port_name="  tgt_port  ",
    )
    assert wire.source_slot_name == "src_slot"
    assert wire.source_port_name == "src_port"
    assert wire.target_slot_name == "tgt_slot"
    assert wire.target_port_name == "tgt_port"


@pytest.mark.unit
@pytest.mark.parametrize("empty", ["", "   "])
@pytest.mark.parametrize(
    "field",
    [
        "source_slot_name",
        "source_port_name",
        "target_slot_name",
        "target_port_name",
    ],
)
def test_template_wire_rejects_empty_field(field: str, empty: str) -> None:
    base = {
        "source_slot_name": "src_slot",
        "source_port_name": "src_port",
        "target_slot_name": "tgt_slot",
        "target_port_name": "tgt_port",
    }
    base[field] = empty
    with pytest.raises(InvalidWireSpecError) as exc_info:
        TemplateWire(**base)
    assert field in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "field",
    [
        "source_slot_name",
        "source_port_name",
        "target_slot_name",
        "target_port_name",
    ],
)
def test_template_wire_rejects_too_long(field: str) -> None:
    base = {
        "source_slot_name": "src_slot",
        "source_port_name": "src_port",
        "target_slot_name": "tgt_slot",
        "target_port_name": "tgt_port",
    }
    base[field] = "x" * (WIRE_PORT_NAME_MAX_LENGTH + 1)
    with pytest.raises(InvalidWireSpecError) as exc_info:
        TemplateWire(**base)
    assert field in str(exc_info.value)


@pytest.mark.unit
def test_template_wire_rejects_degenerate_full_self_loop() -> None:
    """Same slot AND same port on both endpoints is a degenerate loop."""
    with pytest.raises(InvalidWireSpecError) as exc_info:
        TemplateWire(
            source_slot_name="lut",
            source_port_name="out",
            target_slot_name="lut",
            target_port_name="out",
        )
    assert "degenerate" in str(exc_info.value).lower()


@pytest.mark.unit
def test_template_wire_allows_self_slot_with_different_ports() -> None:
    """PandABox LUT pattern: same slot, different ports is allowed."""
    wire = TemplateWire(
        source_slot_name="lut",
        source_port_name="out",
        target_slot_name="lut",
        target_port_name="feedback_in",
    )
    assert wire.source_slot_name == wire.target_slot_name
    assert wire.source_port_name != wire.target_port_name


@pytest.mark.unit
def test_template_wire_is_frozen() -> None:
    wire = TemplateWire(
        source_slot_name="src",
        source_port_name="out",
        target_slot_name="tgt",
        target_port_name="in",
    )
    with pytest.raises(Exception):  # noqa: B017
        wire.source_slot_name = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_template_wire_dedup_by_full_4_tuple() -> None:
    """Identity IS the 4-tuple; frozenset dedupes on it."""
    wire_a = TemplateWire("src", "out", "tgt", "in")
    wire_b = TemplateWire("src", "out", "tgt", "in")
    assert frozenset({wire_a, wire_b}) == frozenset({wire_a})

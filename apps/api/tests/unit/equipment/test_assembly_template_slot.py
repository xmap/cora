"""Unit tests for the TemplateSlot value object."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    InvalidSlotCardinalityError,
    InvalidTemplateSlotError,
    SlotCardinality,
    SlotName,
    TemplateSlot,
)


@pytest.mark.unit
def test_template_slot_minimal_construction() -> None:
    family_id = uuid4()
    slot = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    assert slot.slot_name.value == "camera"
    assert slot.required_family_ids == frozenset({family_id})
    assert slot.cardinality == SlotCardinality.EXACTLY_1
    assert slot.default_settings is None
    assert slot.default_placement is None


@pytest.mark.unit
def test_template_slot_rejects_empty_required_family_ids() -> None:
    with pytest.raises(InvalidTemplateSlotError) as exc_info:
        TemplateSlot(
            slot_name=SlotName("orphan"),
            required_family_ids=frozenset(),
            cardinality=SlotCardinality.ZERO_OR_MORE,
        )
    assert "at least one Family" in str(exc_info.value)


@pytest.mark.unit
def test_template_slot_rejects_non_enum_cardinality() -> None:
    """Closed-enum discipline: cardinality MUST be a SlotCardinality
    member. A raw string would silently bypass the enum contract."""
    from uuid import uuid4

    with pytest.raises(InvalidSlotCardinalityError) as exc_info:
        TemplateSlot(
            slot_name=SlotName("camera"),
            required_family_ids=frozenset({uuid4()}),
            cardinality="Exactly1",  # type: ignore[arg-type]
        )
    assert "Exactly1" in str(exc_info.value)


@pytest.mark.unit
def test_template_slot_accepts_multiple_required_family_ids() -> None:
    """Slot may be satisfied by an Asset carrying any one of N Families."""
    families = frozenset({uuid4(), uuid4(), uuid4()})
    slot = TemplateSlot(
        slot_name=SlotName("either_kind"),
        required_family_ids=families,
        cardinality=SlotCardinality.ZERO_OR_ONE,
    )
    assert slot.required_family_ids == families


@pytest.mark.unit
def test_template_slot_carries_default_settings() -> None:
    slot = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
        default_settings={"exposure_ms": 100, "binning": 1},
    )
    assert slot.default_settings == {"exposure_ms": 100, "binning": 1}


@pytest.mark.unit
def test_template_slot_is_frozen() -> None:
    slot = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    with pytest.raises(Exception):  # noqa: B017  # FrozenInstanceError
        slot.cardinality = SlotCardinality.ZERO_OR_ONE  # type: ignore[misc]


@pytest.mark.unit
def test_template_slot_dedup_by_full_value() -> None:
    """Frozenset dedupes on whole-record equality, NOT slot_name."""
    family_id = uuid4()
    slot_a = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    slot_b = TemplateSlot(
        slot_name=SlotName("camera"),
        required_family_ids=frozenset({family_id}),
        cardinality=SlotCardinality.EXACTLY_1,
    )
    assert frozenset({slot_a, slot_b}) == frozenset({slot_a})

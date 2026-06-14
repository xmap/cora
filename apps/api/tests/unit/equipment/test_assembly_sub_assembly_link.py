"""Unit tests for the SubAssemblyLink value object."""

from uuid import uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    InvalidSubAssemblyLinkError,
    SlotName,
    SubAssemblyLink,
)

_HASH = "sha256:" + "a" * 8


@pytest.mark.unit
def test_sub_assembly_link_minimal_construction() -> None:
    child_id = uuid4()
    link = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=child_id,
        content_hash=_HASH,
    )
    assert link.slot_name.value == "optics"
    assert link.sub_assembly_id == child_id
    assert link.content_hash == _HASH


@pytest.mark.unit
def test_sub_assembly_link_rejects_empty_content_hash() -> None:
    """A link MUST pin a non-empty child revision; a blank pin cannot
    identify a version."""
    with pytest.raises(InvalidSubAssemblyLinkError) as exc_info:
        SubAssemblyLink(
            slot_name=SlotName("optics"),
            sub_assembly_id=uuid4(),
            content_hash="   ",
        )
    assert "non-empty content_hash" in str(exc_info.value)


@pytest.mark.unit
def test_sub_assembly_link_is_frozen() -> None:
    link = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=uuid4(),
        content_hash=_HASH,
    )
    with pytest.raises(Exception):  # noqa: B017  # FrozenInstanceError
        link.content_hash = "other"  # type: ignore[misc]


@pytest.mark.unit
def test_sub_assembly_link_dedup_by_full_value() -> None:
    """Frozenset dedupes on whole-record equality."""
    child_id = uuid4()
    link_a = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=child_id, content_hash=_HASH
    )
    link_b = SubAssemblyLink(
        slot_name=SlotName("optics"), sub_assembly_id=child_id, content_hash=_HASH
    )
    assert frozenset({link_a, link_b}) == frozenset({link_a})


@pytest.mark.unit
def test_sub_assembly_link_distinct_by_pinned_hash() -> None:
    """Two links to the same child but different pinned hashes are
    distinct records: re-pinning is a different structural fact."""
    child_id = uuid4()
    link_a = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=child_id,
        content_hash="sha256:" + "a" * 8,
    )
    link_b = SubAssemblyLink(
        slot_name=SlotName("optics"),
        sub_assembly_id=child_id,
        content_hash="sha256:" + "b" * 8,
    )
    assert frozenset({link_a, link_b}) != frozenset({link_a})

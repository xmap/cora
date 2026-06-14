"""Unit tests for resolve_sub_assembly_pins (the define/version handler helper)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    AssemblyDefined,
    AssemblyName,
    SlotCardinality,
    SlotName,
    SubAssemblyLink,
    SubAssemblyResolution,
    TemplateSlot,
    event_type_name,
    resolve_sub_assembly_pins,
    to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


def _leaf_slot(name: str) -> TemplateSlot:
    return TemplateSlot(
        slot_name=SlotName(name),
        required_family_ids=frozenset({uuid4()}),
        cardinality=SlotCardinality.EXACTLY_1,
    )


async def _seed_assembly(
    store: InMemoryEventStore,
    assembly_id: UUID,
    content_hash: str,
    *,
    slots: frozenset[TemplateSlot] = frozenset(),
    sub_assemblies: frozenset[SubAssemblyLink] = frozenset(),
) -> None:
    event = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Optics"),
        presents_as_family_id=uuid4(),
        required_slots=slots,
        required_wires=frozenset(),
        required_sub_assemblies=sub_assemblies,
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash=content_hash,
        occurred_at=_NOW,
    )
    await store.append(
        stream_type="Assembly",
        stream_id=assembly_id,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(event),
                payload=to_payload(event),
                occurred_at=_NOW,
                event_id=uuid4(),
                command_name="DefineAssembly",
                correlation_id=uuid4(),
                causation_id=None,
                principal_id=uuid4(),
            )
        ],
    )


@pytest.mark.unit
async def test_resolve_classifies_missing_match_and_mismatch() -> None:
    store = InMemoryEventStore()
    matched, drifted, gone = uuid4(), uuid4(), uuid4()
    await _seed_assembly(store, matched, "sha256:" + "a" * 8)
    await _seed_assembly(store, drifted, "sha256:" + "a" * 8)
    refs = frozenset(
        {
            SubAssemblyLink(
                slot_name=SlotName("optics"),
                sub_assembly_id=matched,
                content_hash="sha256:" + "a" * 8,
            ),
            SubAssemblyLink(
                slot_name=SlotName("readout"),
                sub_assembly_id=drifted,
                content_hash="sha256:" + "b" * 8,
            ),
            SubAssemblyLink(
                slot_name=SlotName("gone"),
                sub_assembly_id=gone,
                content_hash="sha256:" + "c" * 8,
            ),
        }
    )
    result = await resolve_sub_assembly_pins(store, refs)
    assert result.missing_ids == frozenset({gone})
    assert result.hash_mismatches == frozenset(
        {(drifted, "sha256:" + "b" * 8, "sha256:" + "a" * 8)}
    )
    assert result.too_deep_ids == frozenset()
    assert result.leaf_slot_collisions == frozenset()


@pytest.mark.unit
async def test_resolve_empty_refs_returns_empty() -> None:
    store = InMemoryEventStore()
    result = await resolve_sub_assembly_pins(store, frozenset())
    assert result == SubAssemblyResolution()


@pytest.mark.unit
async def test_resolve_loads_shared_child_once_and_classifies_each_ref() -> None:
    """Two links to the SAME child id (distinct slot_names): the child
    is loaded once, and each ref is classified on its own pin."""
    store = InMemoryEventStore()
    child = uuid4()
    await _seed_assembly(store, child, "sha256:" + "a" * 8)
    refs = frozenset(
        {
            SubAssemblyLink(
                slot_name=SlotName("optics_a"),
                sub_assembly_id=child,
                content_hash="sha256:" + "a" * 8,
            ),
            SubAssemblyLink(
                slot_name=SlotName("optics_b"),
                sub_assembly_id=child,
                content_hash="sha256:" + "b" * 8,
            ),
        }
    )
    result = await resolve_sub_assembly_pins(store, refs)
    assert result.missing_ids == frozenset()
    assert result.hash_mismatches == frozenset({(child, "sha256:" + "b" * 8, "sha256:" + "a" * 8)})


@pytest.mark.unit
async def test_resolve_flags_child_that_is_itself_a_composite_as_too_deep() -> None:
    """A child carrying its own required_sub_assemblies is too deep:
    register_fixture cannot expand it, so authoring must reject it."""
    store = InMemoryEventStore()
    grandchild, child = uuid4(), uuid4()
    await _seed_assembly(store, grandchild, "sha256:" + "g" * 8)
    child_hash = "sha256:" + "c" * 8
    await _seed_assembly(
        store,
        child,
        child_hash,
        sub_assemblies=frozenset(
            {
                SubAssemblyLink(
                    slot_name=SlotName("inner"),
                    sub_assembly_id=grandchild,
                    content_hash="sha256:" + "g" * 8,
                )
            }
        ),
    )
    refs = frozenset(
        {
            SubAssemblyLink(
                slot_name=SlotName("optics"),
                sub_assembly_id=child,
                content_hash=child_hash,
            )
        }
    )
    result = await resolve_sub_assembly_pins(store, refs)
    assert result.too_deep_ids == frozenset({child})
    assert result.missing_ids == frozenset()
    assert result.hash_mismatches == frozenset()
    # A too-deep child is excluded from the collision scan.
    assert result.leaf_slot_collisions == frozenset()


@pytest.mark.unit
async def test_resolve_flags_leaf_slot_collision_across_two_children() -> None:
    store = InMemoryEventStore()
    left, right = uuid4(), uuid4()
    left_hash, right_hash = "sha256:" + "l" * 8, "sha256:" + "r" * 8
    await _seed_assembly(store, left, left_hash, slots=frozenset({_leaf_slot("camera")}))
    await _seed_assembly(store, right, right_hash, slots=frozenset({_leaf_slot("camera")}))
    refs = frozenset(
        {
            SubAssemblyLink(slot_name=SlotName("a"), sub_assembly_id=left, content_hash=left_hash),
            SubAssemblyLink(
                slot_name=SlotName("b"), sub_assembly_id=right, content_hash=right_hash
            ),
        }
    )
    result = await resolve_sub_assembly_pins(store, refs)
    assert result.leaf_slot_collisions == frozenset({"camera"})


@pytest.mark.unit
async def test_resolve_flags_leaf_slot_collision_against_parent_slot() -> None:
    store = InMemoryEventStore()
    child = uuid4()
    child_hash = "sha256:" + "c" * 8
    await _seed_assembly(store, child, child_hash, slots=frozenset({_leaf_slot("camera")}))
    refs = frozenset(
        {
            SubAssemblyLink(
                slot_name=SlotName("optics"), sub_assembly_id=child, content_hash=child_hash
            )
        }
    )
    result = await resolve_sub_assembly_pins(store, refs, parent_slot_names=frozenset({"camera"}))
    assert result.leaf_slot_collisions == frozenset({"camera"})

"""Unit tests for resolve_sub_assembly_pins (the define/version handler helper)."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.assembly import (
    AssemblyDefined,
    AssemblyName,
    SlotName,
    SubAssemblyLink,
    event_type_name,
    resolve_sub_assembly_pins,
    to_payload,
)
from cora.infrastructure.adapters.in_memory_event_store import InMemoryEventStore
from cora.infrastructure.event_envelope import to_new_event

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)


async def _seed_assembly(store: InMemoryEventStore, assembly_id: UUID, content_hash: str) -> None:
    event = AssemblyDefined(
        assembly_id=assembly_id,
        name=AssemblyName("Optics"),
        presents_as_family_id=uuid4(),
        required_slots=frozenset(),
        required_wires=frozenset(),
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
    missing, mismatches = await resolve_sub_assembly_pins(store, refs)
    assert missing == frozenset({gone})
    assert mismatches == frozenset({(drifted, "sha256:" + "b" * 8, "sha256:" + "a" * 8)})


@pytest.mark.unit
async def test_resolve_empty_refs_returns_empty() -> None:
    store = InMemoryEventStore()
    missing, mismatches = await resolve_sub_assembly_pins(store, frozenset())
    assert missing == frozenset()
    assert mismatches == frozenset()


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
    missing, mismatches = await resolve_sub_assembly_pins(store, refs)
    assert missing == frozenset()
    assert mismatches == frozenset({(child, "sha256:" + "b" * 8, "sha256:" + "a" * 8)})

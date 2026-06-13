"""Read repository for the Assembly aggregate.

`load_assembly(event_store, assembly_id) -> Assembly | None` mirrors
`load_mount` / `load_frame` / `load_asset`. Used by update-style
commands (`version_assembly`, `deprecate_assembly`,
`register_fixture`) that need to load + fold before deciding.

`resolve_sub_assembly_pins` is the shared cross-aggregate check that
the `define_assembly` and `version_assembly` handlers run over a
command's `sub_assembly_refs`: it loads each referenced child
Assembly and classifies whether it exists and whether its current
content_hash still matches the pin the parent was authored against.
"""

import asyncio
from uuid import UUID

from cora.equipment.aggregates.assembly.events import from_stored
from cora.equipment.aggregates.assembly.evolver import fold
from cora.equipment.aggregates.assembly.state import Assembly, SubAssemblyLink
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Assembly"


async def load_assembly(event_store: EventStore, assembly_id: UUID) -> Assembly | None:
    """Load and fold an Assembly's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, assembly_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def resolve_sub_assembly_pins(
    event_store: EventStore,
    refs: frozenset[SubAssemblyLink],
) -> tuple[frozenset[UUID], frozenset[tuple[UUID, str, str | None]]]:
    """Classify a command's sub-assembly references against the store.

    Returns `(missing_ids, hash_mismatches)`:
      - `missing_ids`: sub_assembly_ids that do not resolve to a
        defined Assembly.
      - `hash_mismatches`: `(sub_assembly_id, pinned, current)` for
        refs whose pinned content_hash differs from the loaded child
        Assembly's current content_hash (snapshot drift; the parent
        must re-pin via a fresh define / version).

    Each distinct sub_assembly_id is loaded once (concurrently); every
    ref is then classified against the loaded state. The decider
    raises `SubAssemblyNotFoundForAssemblyError` /
    `SubAssemblyContentHashMismatchError` from these sets, so the
    handler stays free of domain-error decisions.
    """
    unique_ids = {ref.sub_assembly_id for ref in refs}
    if not unique_ids:
        return frozenset(), frozenset()
    ordered = sorted(unique_ids, key=str)
    loaded = await asyncio.gather(*(load_assembly(event_store, sub_id) for sub_id in ordered))
    by_id = dict(zip(ordered, loaded, strict=True))
    missing = frozenset(sub_id for sub_id in unique_ids if by_id[sub_id] is None)
    mismatches: set[tuple[UUID, str, str | None]] = set()
    for ref in refs:
        child = by_id[ref.sub_assembly_id]
        if child is not None and child.content_hash != ref.content_hash:
            mismatches.add((ref.sub_assembly_id, ref.content_hash, child.content_hash))
    return missing, frozenset(mismatches)

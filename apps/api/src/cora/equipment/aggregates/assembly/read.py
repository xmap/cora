"""Read repository for the Assembly aggregate.

`load_assembly(event_store, assembly_id) -> Assembly | None` mirrors
`load_mount` / `load_frame` / `load_asset`. Used by update-style
commands (`version_assembly`, `deprecate_assembly`,
`register_fixture`) that need to load + fold before deciding.

`resolve_sub_assembly_pins` is the shared cross-aggregate check that
the `define_assembly` and `version_assembly` handlers run over a
command's `required_sub_assemblies`: it loads each referenced child
Assembly once and classifies every problem the authoring path must
reject before a parent blueprint is written. It returns a
`SubAssemblyResolution` so the classifications stay named rather than
positional as the set of checks grows.
"""

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.assembly.events import from_stored
from cora.equipment.aggregates.assembly.evolver import fold
from cora.equipment.aggregates.assembly.state import Assembly, SubAssemblyLink
from cora.infrastructure.ports import EventStore

_STREAM_TYPE = "Assembly"


@dataclass(frozen=True)
class SubAssemblyResolution:
    """Cross-aggregate classification of a command's sub-assembly refs.

    Every field is computed from the SAME single load of each
    referenced child, so the authoring path (define / version) rejects
    the same shapes `register_fixture` rejects, but at authoring time
    where the operator can still act.

      - `missing_ids`: sub_assembly_ids that do not resolve to a
        defined Assembly.
      - `hash_mismatches`: `(sub_assembly_id, pinned, current)` for
        refs whose pinned content_hash has drifted from the loaded
        child's current content_hash (snapshot drift; the parent must
        re-pin via a fresh define / version).
      - `too_deep_ids`: sub_assembly_ids of children that THEMSELVES
        declare `required_sub_assemblies`. One composing level is
        supported, so a child-of-a-child makes the parent
        un-instantiable; rejecting at authoring time keeps "a defined
        Assembly is always instantiable" a real invariant and, since a
        non-leaf child is refused, closes the A->B->A indirect-cycle
        hole for the two-node case.
      - `leaf_slot_collisions`: leaf slot_names that appear in more
        than one composed blueprint once the parent's own leaf slots
        and every leaf child's leaf slots are merged into the single
        flat namespace `register_fixture` materializes. Surfacing here
        means the operator does not discover the clash only at the end
        of the install-then-register choreography.
    """

    missing_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    hash_mismatches: frozenset[tuple[UUID, str, str | None]] = field(
        default_factory=frozenset[tuple[UUID, str, str | None]]
    )
    too_deep_ids: frozenset[UUID] = field(default_factory=frozenset[UUID])
    leaf_slot_collisions: frozenset[str] = field(default_factory=frozenset[str])


async def load_assembly(event_store: EventStore, assembly_id: UUID) -> Assembly | None:
    """Load and fold an Assembly's event stream into current state."""
    stored, _version = await event_store.load(_STREAM_TYPE, assembly_id)
    events = [from_stored(s) for s in stored]
    return fold(events)


async def resolve_sub_assembly_pins(
    event_store: EventStore,
    refs: frozenset[SubAssemblyLink],
    *,
    parent_slot_names: frozenset[str] = frozenset(),
) -> SubAssemblyResolution:
    """Classify a command's sub-assembly references against the store.

    Each distinct sub_assembly_id is loaded once (concurrently); every
    ref is then classified into the four fields of
    `SubAssemblyResolution`. The decider raises the matching
    sorted-first error from each set, so the handler stays free of
    domain-error decisions.

    `parent_slot_names` is the parent command's own leaf slot_names; it
    seeds the flat namespace used to detect `leaf_slot_collisions`
    across the parent and its (leaf) children, mirroring the union that
    `register_fixture` builds at materialization time. Missing and
    too-deep children are excluded from the collision scan because they
    are rejected on their own grounds first.
    """
    unique_ids = {ref.sub_assembly_id for ref in refs}
    if not unique_ids:
        return SubAssemblyResolution()
    ordered = sorted(unique_ids, key=str)
    loaded = await asyncio.gather(*(load_assembly(event_store, sub_id) for sub_id in ordered))
    by_id = dict(zip(ordered, loaded, strict=True))

    missing = frozenset(sub_id for sub_id in unique_ids if by_id[sub_id] is None)
    too_deep = frozenset(
        sub_id
        for sub_id in unique_ids
        if (child := by_id[sub_id]) is not None and child.required_sub_assemblies
    )

    mismatches: set[tuple[UUID, str, str | None]] = set()
    for ref in refs:
        child = by_id[ref.sub_assembly_id]
        if child is not None and child.content_hash != ref.content_hash:
            mismatches.add((ref.sub_assembly_id, ref.content_hash, child.content_hash))

    # Replay register_fixture's flat-namespace union: seed with the
    # parent's own leaf slots, then fold in each leaf child's leaf
    # slots, recording any name that lands on a name already seen. Only
    # leaf children participate; missing / too-deep children are
    # rejected before the materialization union would ever form.
    seen_names = set(parent_slot_names)
    collisions: set[str] = set()
    for sub_id in ordered:
        child = by_id[sub_id]
        if child is None or child.required_sub_assemblies:
            continue
        for slot in sorted(child.required_slots, key=lambda s: s.slot_name.value):
            name = slot.slot_name.value
            if name in seen_names:
                collisions.add(name)
            else:
                seen_names.add(name)

    return SubAssemblyResolution(
        missing_ids=missing,
        hash_mismatches=frozenset(mismatches),
        too_deep_ids=too_deep,
        leaf_slot_collisions=frozenset(collisions),
    )

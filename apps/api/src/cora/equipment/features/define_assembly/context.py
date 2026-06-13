"""Context snapshot loaded by the define_assembly handler.

The define_assembly slice uses single-stream-write + projection-
precondition (per project_mount_frame_design install_asset
precedent). The handler loads each referenced FamilyId via
`load_family` before calling the decider; the context VO carries
the set of FamilyIds that did NOT resolve to a defined Family.

`missing_family_ids` empty means all referenced Families exist (the
decider can proceed). When non-empty, the decider raises
FamilyNotFoundForAssemblyError carrying the sorted-first missing id
so error responses are stable across runs; surfacing the full set
on a single error would force the route layer to encode a list shape
that no shipped error currently uses.

The same handler also resolves each `sub_assembly_refs` link via
`resolve_sub_assembly_pins`: `missing_sub_assembly_ids` carries the
referenced child Assembly ids that do not resolve, and
`sub_assembly_hash_mismatches` carries `(sub_assembly_id, pinned,
current)` for refs whose pinned content_hash has drifted from the
child's current content_hash. The decider raises the matching
sorted-first error from each set.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DefineAssemblyContext:
    """Snapshot of FamilyId + sub-assembly existence/pin checks for define_assembly."""

    missing_family_ids: frozenset[UUID]
    missing_sub_assembly_ids: frozenset[UUID] = frozenset()
    sub_assembly_hash_mismatches: frozenset[tuple[UUID, str, str | None]] = frozenset()

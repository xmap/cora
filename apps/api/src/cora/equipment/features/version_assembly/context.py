"""Context snapshot loaded by the version_assembly handler.

Same shape as DefineAssemblyContext: the handler loads each
referenced FamilyId via `load_family` before calling the decider;
the context VO carries the set of FamilyIds that did NOT resolve
to a defined Family.

`missing_family_ids` empty means all referenced Families exist.
When non-empty, the decider raises FamilyNotFoundForAssemblyError
carrying the sorted-first missing id so error responses are stable
across runs.

The handler also resolves each `required_sub_assemblies` link via
`resolve_sub_assembly_pins`, which returns a `SubAssemblyResolution`
whose four classifications map one-to-one onto the context fields
below: `sub_assembly_missing_ids` (child does not resolve),
`sub_assembly_hash_mismatches` (`(sub_assembly_id, pinned, current)`
for a drifted pin), `sub_assembly_too_deep_ids` (child is itself a
composite, so the parent would be un-instantiable), and
`sub_assembly_leaf_collisions` (a leaf slot_name appears in more than
one composed blueprint once the union is materialized).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionAssemblyContext:
    """Snapshot of Role + FamilyId + sub-assembly existence/pin/depth/collision checks."""

    missing_family_ids: frozenset[UUID]
    missing_role_ids: frozenset[UUID] = frozenset()
    sub_assembly_missing_ids: frozenset[UUID] = frozenset()
    sub_assembly_hash_mismatches: frozenset[tuple[UUID, str, str | None]] = frozenset()
    sub_assembly_too_deep_ids: frozenset[UUID] = frozenset()
    sub_assembly_leaf_collisions: frozenset[str] = frozenset()

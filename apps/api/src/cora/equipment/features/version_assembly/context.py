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
`resolve_sub_assembly_pins`: `missing_sub_assembly_ids` carries the
referenced child Assembly ids that do not resolve, and
`sub_assembly_hash_mismatches` carries `(sub_assembly_id, pinned,
current)` for refs whose pinned content_hash has drifted from the
child's current content_hash.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionAssemblyContext:
    """Snapshot of FamilyId + sub-assembly existence/pin checks for version_assembly."""

    missing_family_ids: frozenset[UUID]
    missing_sub_assembly_ids: frozenset[UUID] = frozenset()
    sub_assembly_hash_mismatches: frozenset[tuple[UUID, str, str | None]] = frozenset()

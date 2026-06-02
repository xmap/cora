"""Context snapshot loaded by the version_assembly handler.

Same shape as DefineAssemblyContext: the handler loads each
referenced FamilyId via `load_family` before calling the decider;
the context VO carries the set of FamilyIds that did NOT resolve
to a defined Family.

`missing_family_ids` empty means all referenced Families exist.
When non-empty, the decider raises FamilyNotFoundForAssemblyError
carrying the sorted-first missing id so error responses are stable
across runs.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class VersionAssemblyContext:
    """Snapshot of FamilyId existence checks for version_assembly."""

    missing_family_ids: frozenset[UUID]

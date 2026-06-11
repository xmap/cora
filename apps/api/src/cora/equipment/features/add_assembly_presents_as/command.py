"""The `AddAssemblyPresentsAs` command -- intent dataclass for this slice.

Mirror of `add_family_presents_as` for the Assembly aggregate. The
handler resolves `role_id` via `RoleLookup` at the edge so the
existence check fires before any decider call; the decider itself
does NOT enforce the affordance-superset gate (deferred to
register_fixture layer per memo Watch item: Assembly affordances
derive from constituent Family union at fixture-time, not template-
time).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddAssemblyPresentsAs:
    """Add a global Role contract to an Assembly's `presents_as` set."""

    assembly_id: UUID
    role_id: UUID

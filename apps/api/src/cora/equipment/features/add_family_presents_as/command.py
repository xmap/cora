"""The `AddFamilyPresentsAs` command -- intent dataclass for this slice.

Family.presents_as mutation: incremental add (single Role per call).
Sibling of `remove_family_presents_as`. Operators add a Role
contract to a Family when commissioning a new role mapping
(MotionController advertises `Controller`, Camera advertises
`Detector`); remove when retiring it.

`family_id` is the target Family aggregate. `role_id` is the global
Role contract being advertised; the handler resolves it via
`RoleLookup` at the edge so the decider can enforce the
affordance-superset check (Family.affordances must superset
Role.required_affordances per memo Lock 17).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AddFamilyPresentsAs:
    """Add a global Role contract to a Family's `presents_as` set."""

    family_id: UUID
    role_id: UUID

"""The `RemoveFamilyPresentsAs` command -- intent dataclass for this slice.

Sibling of `add_family_presents_as`. Withdraws a single Role
contract from the Family's `presents_as` set. The decider does NOT
consult `RoleLookup`: a Role that no longer resolves may still
have been previously advertised, and the operator can withdraw it
cleanly without round-tripping through the Role projection.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveFamilyPresentsAs:
    """Remove a global Role contract from a Family's `presents_as` set."""

    family_id: UUID
    role_id: UUID

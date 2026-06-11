"""The `RemoveAssemblyPresentsAs` command -- intent dataclass for this slice.

Sibling of `add_assembly_presents_as`. Withdraws a single Role
contract from the Assembly's `presents_as` set. The decider does
NOT consult `RoleLookup`: a Role that no longer resolves may still
have been previously advertised.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RemoveAssemblyPresentsAs:
    """Remove a global Role contract from an Assembly's `presents_as` set."""

    assembly_id: UUID
    role_id: UUID

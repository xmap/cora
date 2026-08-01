"""The `DeprecateFamily` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Single-
Carries family_id plus a required closed
`DeprecationReason`.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateFamily:
    """Mark an existing family as deprecated."""

    family_id: UUID
    reason: DeprecationReason

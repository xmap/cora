"""The `DeprecateFamily` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Single-
field command (just family_id); no body at the API layer.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateFamily:
    """Mark an existing family as deprecated."""

    family_id: UUID
    reason: DeprecationReason

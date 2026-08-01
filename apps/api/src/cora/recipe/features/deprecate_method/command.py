"""The `DeprecateMethod` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Single-
Carries method_id plus a required closed
`DeprecationReason`. Mirrors
`DeprecateFamily` (Equipment 5f-2) shape.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateMethod:
    """Mark an existing method as deprecated."""

    method_id: UUID
    reason: DeprecationReason

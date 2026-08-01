"""The `DeprecatePractice` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Single-
Carries practice_id plus a required closed
`DeprecationReason`. Mirrors
`DeprecateMethod` / `DeprecateFamily`.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecatePractice:
    """Mark an existing practice as deprecated."""

    practice_id: UUID
    reason: DeprecationReason

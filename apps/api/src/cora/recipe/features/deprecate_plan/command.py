"""The `DeprecatePlan` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Single-
Carries plan_id plus a required closed
`DeprecationReason`. Mirrors
`DeprecatePractice` / `DeprecateMethod` / `DeprecateFamily`.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecatePlan:
    """Mark an existing plan as deprecated."""

    plan_id: UUID
    reason: DeprecationReason

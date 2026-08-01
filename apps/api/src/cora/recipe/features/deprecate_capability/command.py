"""The `DeprecateCapability` command — intent dataclass for this slice.

Multi-source transition: Defined | Versioned -> Deprecated. Carries
the target Capability id + an optional `replaced_by_capability_id`
pointer for the successor (LOINC `MAP_TO` precedent). When None,
this is deprecated-without-replacement.

Existing Methods/Procedures that reference the deprecated Capability
are NOT automatically invalidated (advisory at BC layer); a future
enhancement may surface a warning at Plan.activate / Procedure.start
time when binding to a Deprecated Capability.
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateCapability:
    """Mark an existing Capability as Deprecated, optionally pointing at a successor."""

    capability_id: UUID
    reason: DeprecationReason
    replaced_by_capability_id: UUID | None = None

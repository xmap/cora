"""The `DeprecateAssembly` command - intent dataclass for the deprecate_assembly slice.

Multi-source transition: Defined | Versioned -> Deprecated (terminal).
Carries the target `assembly_id` plus an operator-supplied `reason`
closed `DeprecationReason` (audit-log evidence; unlike decommission_mount's
reason field).

Once Deprecated, the Assembly stream rejects further mutations:
`version_assembly` raises AssemblyCannotVersionError, future
`instantiate_assembly` raises AssemblyCannotInstantiateError, and
re-`deprecate_assembly` is strict-not-idempotent (raises
AssemblyCannotDeprecateError carrying the current status).
"""

from dataclasses import dataclass
from uuid import UUID

from cora.shared.deprecation import DeprecationReason


@dataclass(frozen=True)
class DeprecateAssembly:
    """Mark an existing Assembly as deprecated."""

    assembly_id: UUID
    reason: DeprecationReason

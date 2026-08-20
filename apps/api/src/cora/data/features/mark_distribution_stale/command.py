"""The `MarkDistributionStale` command, intent dataclass for this slice.

Records that the bytes for one storage-tier copy of a Dataset are known
to be gone or no longer trusted (a storage array failure, a bit-rot
finding, or any other grounds an operator has). Carries the target
distribution's id plus a free-form `reason` string (1-500 chars after
trim; validated at the API boundary AND defensively at the decider via
`DistributionMarkStaleReason` VO).

Unlike `discard_distribution`, this command RECORDS A FACT ABOUT THE
WORLD THAT ALREADY HAPPENED; it is not a deliberate act CORA is entitled
to refuse. The only guard is structural: the Distribution must exist
and must not already be Discarded (terminal). There is no redundancy
guard and no parent-Dataset guard.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class MarkDistributionStale:
    """Mark a Distribution copy Stale (any non-Discarded status -> Stale)."""

    distribution_id: UUID
    reason: str

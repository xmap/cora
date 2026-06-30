"""The `DiscardDistribution` command, intent dataclass for this slice.

Marks one storage-tier copy of a Dataset as Discarded. Carries the
target distribution's id plus an operator-supplied free-form `reason`
string (1-500 chars after trim; validated at the API boundary AND
defensively at the decider via `DistributionDiscardReason` VO).

Metadata-only, same posture as `discard_dataset`: the bytes for this
copy are reclaimed out-of-band (an operator workflow against S3 /
Globus / POSIX); this event records the reclaim decision + reason for
audit. The Data BC does NOT issue the storage deletion itself.

The guarded primitive: a copy may be discarded only when a sibling
copy of the same Dataset is Verified on a different storage tier, and
the parent Dataset is not itself Discarded. The decider enforces both.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DiscardDistribution:
    """Discard an existing Distribution copy (any prior status -> Discarded)."""

    distribution_id: UUID
    reason: str

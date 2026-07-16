"""The `DenyRatification` command -- intent dataclass for this slice.

Transition command: Requested -> Denied. The refusing principal is the envelope
`principal_id`, threaded into the decider by the handler, NOT a command field.
Carries an operator-supplied `reason` (1-500 chars after trim).
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class DenyRatification:
    """Refuse (deny) a pending ratification.

    `ratification_id`: REQUIRED id of the Requested ratification to deny.
    `reason`: REQUIRED operator-supplied reason (1-500 chars after trim).
    """

    ratification_id: UUID
    reason: str

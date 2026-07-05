"""The `GrantRatification` command -- intent dataclass for this slice.

Transition command: Requested -> Granted. The co-signing principal is the
envelope `principal_id`, threaded into the decider by the handler, NOT a command
field, so a caller cannot claim a different co-signer. Mirrors the
`supersede_caution` author-threading convention.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class GrantRatification:
    """Co-sign (grant) a pending ratification.

    `ratification_id`: REQUIRED id of the Requested ratification to grant.
    """

    ratification_id: UUID

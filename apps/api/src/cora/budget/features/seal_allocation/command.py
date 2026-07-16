"""The `SealAllocation` command -- intent dataclass for this slice.

Closes an Active envelope's books: `Active -> Sealed`, terminal. The
final-spend snapshot is NOT on the command: the handler computes it
at seal time by folding the inference ledger over the envelope's own
window (`activated_at` to the seal instant) via the injected
TotalSpendReader, so a caller can never assert a figure the ledger
does not support. The CampaignClosed subscriber and the REST
route both drive this one slice.

`reason` is optional: a routine end-of-window seal needs no
justification, an early close usually carries context. The sealing
actor's identity is injected by the handler from the envelope's
`principal_id` (the decider's `sealed_by` kwarg); no actor field on
the command.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SealAllocation:
    """Seal an Active Allocation (`Active -> Sealed`, closing the books)."""

    allocation_id: UUID
    reason: str | None = None

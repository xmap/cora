"""The `IngestScan` command for this slice.

Carries what the caller knows that the file cannot say: where the file
is (`locator`, interpreted by the deployment's ScanReader adapter),
which Asset produced it, which storage Supply holds it and over what
access protocol, and optionally which Run it belongs to.

`captured_at` is the operator-asserted acquisition time, allowed ONLY
when the file itself carries no parseable timestamp; a parseable file
value always wins, and supplying both is refused as ambiguous rather
than silently overridden. This mirrors the trust surface the base
`record_acquisition` slice already ships (captured_at is caller-asserted
provenance there), so an operator naming the capture time from the
logbook is nothing new; a machine fabricating one from the ingest clock
would be, which is why no such fallback exists.

Everything else the three composed commands need (name, checksum,
byte size, media type, frame accounting) is read or computed, never
caller-supplied: the file and its digest are the authority on their own
facts.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class IngestScan:
    """Ingest one finished scan file into Dataset + Distribution +
    Acquisition, atomically."""

    locator: str
    producing_asset_id: UUID
    supply_id: UUID
    access_protocol: str
    producing_run_id: UUID | None = None
    captured_at: datetime | None = None

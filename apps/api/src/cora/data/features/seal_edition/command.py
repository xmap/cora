"""The `SealEdition` command for the seal_edition slice.

Carries the caller's intent at seal-time:

  - `edition_id`: the Edition to seal
  - `publisher_facility_code`: optional override (when set, overrides
    any value the operator supplied at register time; resolved via
    `FacilityLookup` at the handler)
  - `publication_year_override`: optional explicit year (defaults to
    the sealing-clock UTC year when None and the Edition has no year
    set at register-time)
  - `license_override`: optional SPDX identifier (used only when the
    Edition has no license at register-time)

Per design memo L33: `content_hash` is NEVER operator-supplied; it
comes from the `EditionSerializer` only.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SealEdition:
    """Seal a Registered Edition: compute content_hash, snapshot members."""

    edition_id: UUID
    publisher_facility_code: str | None = None
    publication_year_override: int | None = None
    license_override: str | None = None

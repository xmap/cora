"""The `RegisterFacility` command: intent dataclass for this slice.

Carries the caller-controlled fields for registering a new Facility:

  - `code`: cross-deployment convergent facility slug (lowercase ASCII
    alphanumeric + dash, 1-32 chars). The handler constructs the
    `FacilityCode` VO at the edge and uses it to derive the stream id
    via `facility_stream_id`; live-path uniqueness is enforced by
    the resulting `ConcurrencyError` on duplicate code.
  - `display_name`: operator-supplied display string, trimmed and
    bounded 1-200 chars via the `FacilityName` VO at handler edge.
  - `kind`: closed `FacilityKind` enum selecting Site or Area.
  - `parent_id`: optional Facility id reference. MUST be None when
    `kind=Site`; MUST be non-None when `kind=Area` (decider enforces
    the structural invariant). Cross-stream parent-existence and
    parent-kind=Site validation are deferred to slice 6 (when the
    FacilityLookup port surface ships).
  - `alternate_identifiers`: optional day-one PIDINST seed (defaults
    to empty frozenset) per Asset precedent. Add/remove slices are
    deferred until operational need surfaces.

Server-side concerns (Facility id derived from code, wall-clock
timestamp, correlation id, per-event ids, `registered_by`) are
injected by the handler from infrastructure ports / the request
envelope. `persistent_id` and `trust_anchor_credential_ids` are NOT
on the command per Sub-Slice A design lock (state-only in slice 5).
"""

from dataclasses import dataclass, field

from cora.federation.aggregates._value_types import FacilityId
from cora.federation.aggregates.facility import FacilityKind
from cora.shared.identifier import AlternateIdentifier


@dataclass(frozen=True, slots=True)
class RegisterFacility:
    """Register a new Facility (genesis; lands in Active)."""

    code: str
    display_name: str
    kind: FacilityKind
    parent_id: FacilityId | None
    alternate_identifiers: frozenset[AlternateIdentifier] = field(
        default_factory=frozenset[AlternateIdentifier]
    )

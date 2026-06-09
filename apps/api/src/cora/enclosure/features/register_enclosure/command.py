"""The `RegisterEnclosure` command: intent dataclass for this slice.

Carries the caller-controlled fields for registering a new Enclosure:

  - `name`: operator-supplied display string for the enclosure (hutch
    label, cabinet label, containment-volume label). Wrapped into the
    `EnclosureName` VO at the decider; the route's Pydantic body bounds
    1-`ENCLOSURE_NAME_MAX_LENGTH` chars and the VO trims + re-validates
    so direct in-process callers (sagas, tests) get the same protection.
  - `containing_asset_id`: bare `UUID` cross-BC opaque pointer to the
    Asset that physically contains this Enclosure (the hutch's beamline
    Asset, the cabinet's instrument Asset). The decider stays pure;
    cross-aggregate existence checks against the Asset BC are deferred
    to the handler layer via a port when operational evidence justifies
    the dependency surface, per the walk-cost evidence collection lock.
    Stored bare on the aggregate per the
    [[project_enclosure_stage1_design]] L-state-3 cross-BC-opaque
    convention.

Server-side concerns (new aggregate id, wall-clock timestamp,
`registered_by`, correlation id, per-event ids) are injected by the
handler from infrastructure ports / the request envelope, matching the
cross-BC create-style command shape locked in Supply / Facility /
Trust / Subject / Equipment. The address tuple `(containing_asset_id,
name)` is enforced unique while lifecycle=Active by the
projection-tier PARTIAL UNIQUE INDEX; the aggregate cannot enforce
cross-stream invariants without DCB and the decider does not
pre-check.

Status is implicit at registration: the genesis evolver sets
`permit_status=EnclosurePermitStatus.UNKNOWN` and
`lifecycle=EnclosureLifecycle.ACTIVE` from the event type rather than
the command payload (Slim Aggregate, L-state-1) per the universal
industrial + cloud-native consensus on registration-time defaults.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RegisterEnclosure:
    """Register a new interlock-gated containment volume (lands in `Unknown`)."""

    name: str
    containing_asset_id: UUID

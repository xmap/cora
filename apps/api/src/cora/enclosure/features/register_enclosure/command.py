"""The `RegisterEnclosure` command: intent dataclass for this slice.

Carries the caller-controlled fields for registering a new Enclosure:

  - `name`: operator-supplied display string for the enclosure (hutch
    label, cabinet label, containment-volume label). Wrapped into the
    `EnclosureName` VO at the decider; the route's Pydantic body bounds
    1-`ENCLOSURE_NAME_MAX_LENGTH` chars and the VO trims + re-validates
    so direct in-process callers (sagas, tests) get the same protection.
  - `facility_code`: bare `str` cross-deployment convergent slug for the
    containing Facility (the Site / Area the enclosure sits within, a
    space-contained-in-a-larger-space relation, NOT an equipment
    pointer). Bare `str` on the command (matches the Permit / Credential
    / Seal / Asset / Supply wire convention of bare-str slugs on
    commands + typed `FacilityCode` VO on aggregate state); the
    route + tool Pydantic regex enforces the `[a-z0-9-]{1,32}` codepoint
    contract at the API boundary. The handler resolves the slug via
    `FacilityLookup.lookup_by_code` BEFORE the decider; the decider
    rejects unknown slugs with `EnclosureFacilityNotFoundError`
    (HTTP 404). Mirrors the `register_asset` / `register_supply`
    facility-binding handler split.

Server-side concerns (new aggregate id, wall-clock timestamp,
`registered_by`, correlation id, per-event ids) are injected by the
handler from infrastructure ports / the request envelope, matching the
cross-BC create-style command shape locked in Supply / Facility /
Trust / Subject / Equipment. The address tuple `(facility_code,
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


@dataclass(frozen=True)
class RegisterEnclosure:
    """Register a new interlock-gated containment volume (lands in `Unknown`)."""

    name: str
    facility_code: str

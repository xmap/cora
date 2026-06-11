"""The `RegisterSupply` command, intent dataclass for this slice.

Carries the caller-controlled fields: free-form `kind` discriminator,
operator-readable `name`, the cross-deployment convergent
`facility_code` binding the supply to its owning
Facility, and the OPTIONAL `containing_asset_id`
physical-equipment containment back-reference. Server-side concerns
(new aggregate id, wall-clock timestamp, correlation id, per-event
ids) are injected by the handler from infrastructure ports, matching
the cross-BC create-style command shape locked in Access / Trust /
Subject / Equipment.

`kind` is bare `str` (free-form, 1-50 chars after trim) per the
[[project_supply_design]] iter-1 lock; closed StrEnum was rejected
universally across the three research corpora; promotion to
`SupplyKind: StrEnum` is a deferred-with-trigger watch item.

`facility_code` is bare `str` on the command (matches the
Permit / Credential / Seal wire convention of bare-str
slugs on commands + typed `FacilityCode` VO on aggregate state).
Route + tool Pydantic regex enforces the `[a-z0-9-]{1,32}` codepoint
contract at the API boundary; the handler wraps in `FacilityCode(...)`
at the port edge before calling `FacilityLookup.lookup_by_code`.

`containing_asset_id` is OPTIONAL: `None` semantically means
"facility-scope resource" (the photon beam, central LN2 plant,
building electrical power); non-None binds the Supply to a specific
Asset in the Equipment BC hierarchy (the containing beamline as
`Asset(tier=Unit)`; site/area scope is the Facility aggregate, bound
via `facility_code`) per
[[project_supply_sector_disposition]] Option A. The handler resolves
it via `AssetLookup.lookup` when present; the decider rejects
unknown ids with `SupplyContainingAssetNotFoundError` (HTTP 404)
and skips validation entirely when None.

Status is implicit at registration (`Unknown`) per universal
industrial + cloud-native consensus and is NOT part of the command;
see the Supply aggregate's `state.py` docstring for the
enum-in-state, derived-from-event-type-in-evolver convention.
"""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class RegisterSupply:
    """Register a new continuously-available resource (lands in `Unknown`)."""

    kind: str
    name: str
    facility_code: str
    containing_asset_id: UUID | None = None

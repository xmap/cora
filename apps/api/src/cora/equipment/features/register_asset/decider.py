"""Pure decider for the `RegisterAsset` command.

Pure function: given the current Asset state (None for a fresh
stream) and a `RegisterAsset` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Anchoring rule

An Asset is anchored exactly one way (XOR over {parent_id, facility_code}):
  - A root Asset binds `facility_code` (its owning Federation
    Facility) and MUST have `parent_id=None`.
  - A non-root Asset has a `parent_id` and MUST NOT bind
    `facility_code` (it inherits facility scope through the tree).

Facility-envelope scope (institution / site / area) is owned by the
`Facility` aggregate (`FacilityKind{Site, Area}`), not by an Asset tier.

Eventual-consistency stance: the decider does NOT verify the
referenced parent Asset exists in the event store. Cycle
detection (target's ancestors must not include this asset)
requires walking the parent chain and is deferred to projection-
worker era. The single-parent tree rule is enforced structurally
(one `parent_id` field, can't be a list).

**Tiers are conventional, not enforced**: the decider does NOT
check that a Device's parent is a Component (etc). Device-in-
Device is allowed when reality demands it (smart instruments
with addressable sub-modules).

## Model binding (Lock B)

`command.model_id` flows through to the emitted AssetRegistered
event without inspection. The decider does NOT load the Model
snapshot: at registration the Asset's families set is empty, so
the cross-BC subset invariant
`Model.declared_family_ids subset-of Asset.family_ids` is vacuously
satisfied and there is nothing to validate against. The handler
enforces Model existence (raises `ModelNotFoundError` -> 404)
before invoking decide; the first meaningful subset enforcement
fires at the first `add_asset_family` call against the bound
Asset.

## Alternate identifiers (Lock D + Lock F + Lock I)

`command.alternate_identifiers` flows through to the emitted
AssetRegistered event verbatim. The decider does NOT validate
`(kind, value)` uniqueness across other Assets in v1 (Lock F):
PIDINST itself admits "should be unique", same-vendor serial
schemes legitimately reappear across facilities, and CORA stays
format-opaque about provenance of the string. Frozenset semantics
on the field structurally forbid duplicate `(kind, value)` pairs
on the same Asset. No cross-BC IO fires on this field's behalf
(Lock I); the handler does not load any external stream.

## Owners (Lock 6 + Lock 11)

`command.owners` flows through to the emitted AssetRegistered
event verbatim. The decider enforces name-uniqueness within the
payload (Lock 6): two owners sharing a `name` raise
`AssetOwnerAlreadyPresentError`. The pairing invariant on
(identifier, identifier_type) is enforced inside the `AssetOwner`
VO's `__post_init__`. No cross-BC IO fires on this field's
behalf; ROR / GRID / ISNI string values are opaque to the
aggregate.

## Controller binding (Lock A precedent)

`command.controller_id` flows through to the emitted
AssetRegistered event verbatim. Mirrors `model_id` and
`parent_id` precedents: the decider does NOT load the controller
Asset snapshot, does NOT verify it exists, and does NOT enforce
that the referenced Asset carries the MotionController Family.
Operators are trusted to register controllers before binding
stages to them; a dangling reference is operator error, not a
domain invariant violation. The handler does not load any external
stream on this field's behalf.

## Enclosure location binding (Lock A precedent)

`command.located_in_enclosure_id` flows through to the emitted
AssetRegistered event verbatim. Mirrors the `controller_id`
precedent exactly: the decider does NOT load the Enclosure
snapshot, does NOT verify it exists, and applies no validation.
The pointer stays a bare opaque UUID so the Equipment BC takes on
no module dependency on the Enclosure BC. The handler does not
load any external stream on this field's behalf.

## Facility binding (Slice 8A)

`command.facility_code` flows through to the emitted AssetRegistered
event via the typed `FacilityCode` VO loaded by the handler. The
handler resolves the slug via `FacilityLookup.lookup_by_code` and
threads `facility_lookup_result: FacilityLookupResult | None` into
the decider. When `command.facility_code` is non-None and the
lookup result is None, the decider raises
`AssetFacilityNotFoundError` (HTTP 404). When `command.facility_code`
is None, the decider skips this validation entirely (facility
binding is OPTIONAL on Asset; not every Asset has a Facility, e.g.
shared spare-parts pool). The lookup-result's `.code` field is folded
onto the event so the event's `facility_code` reflects the
projection's canonical typed VO, not a command-echo (mirrors the
Supply Slice 7A handler/decider split).
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlreadyExistsError,
    AssetFacilityNotFoundError,
    AssetName,
    AssetOwnerAlreadyPresentError,
    AssetRegistered,
    InvalidAssetParentError,
)
from cora.equipment.features.register_asset.command import RegisterAsset
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.identity import ActorId


def decide(
    state: Asset | None,
    command: RegisterAsset,
    *,
    now: datetime,
    new_id: UUID,
    commissioned_by: ActorId,
    facility_lookup_result: FacilityLookupResult | None,
) -> list[AssetRegistered]:
    """Decide the events produced by registering a new asset.

    Invariants:
      - State must be None (genesis-only) -> AssetAlreadyExistsError
      - Name must be valid -> InvalidAssetNameError
        (via AssetName VO)
      - Anchoring XOR: exactly one of {parent_id, facility_code}.
        A root Asset (parent_id=None) must bind facility_code; a
        non-root (with parent_id) must NOT bind facility_code
        -> InvalidAssetParentError
      - Owner names must be unique within the payload (Lock 6)
        -> AssetOwnerAlreadyPresentError
      - When command.facility_code is non-None,
        facility_lookup_result must be non-None
        -> AssetFacilityNotFoundError
    """
    if state is not None:
        raise AssetAlreadyExistsError(state.id)

    if command.facility_code is not None and facility_lookup_result is None:
        raise AssetFacilityNotFoundError(command.facility_code)

    name = AssetName(command.name)  # validates + trims; raises InvalidAssetNameError

    # Anchoring rule: an Asset is either facility-rooted or parent-nested.
    # Exactly one of {parent_id, facility_code} is set. Facility-envelope
    # scope is owned by the Facility aggregate, not by an Asset tier.
    if command.parent_id is None and command.facility_code is None:
        msg = (
            "Root Asset (parent_id=None) must bind a facility_code (its owning Federation Facility)"
        )
        raise InvalidAssetParentError(msg)
    if command.parent_id is not None and command.facility_code is not None:
        msg = (
            f"Non-root Asset (parent_id={command.parent_id}) must not also bind "
            "facility_code (children inherit facility scope through the tree)"
        )
        raise InvalidAssetParentError(msg)

    # Owner-name uniqueness within the payload (Lock 6). Frozenset
    # semantics already deduplicate full-VO equality but two distinct
    # AssetOwner VOs may share `name` while differing on optional
    # fields; the keying choice forbids that on a single Asset.
    seen_owner_names: set[str] = set()
    for owner in command.owners:
        if owner.name.value in seen_owner_names:
            raise AssetOwnerAlreadyPresentError(new_id, owner.name)
        seen_owner_names.add(owner.name.value)

    return [
        AssetRegistered(
            asset_id=new_id,
            name=name.value,
            tier=command.tier.value,
            parent_id=command.parent_id,
            occurred_at=now,
            commissioned_by=commissioned_by,
            drawing=command.drawing,
            model_id=command.model_id,
            alternate_identifiers=command.alternate_identifiers,
            owners=command.owners,
            controller_id=command.controller_id,
            located_in_enclosure_id=command.located_in_enclosure_id,
            facility_code=(
                facility_lookup_result.code if facility_lookup_result is not None else None
            ),
        )
    ]

"""Pure decider for the `RegisterAsset` command.

Pure function: given the current Asset state (None for a fresh
stream) and a `RegisterAsset` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Hierarchy rule

Per the BC map's hierarchy semantics:
  - `Enterprise` is the root level — `parent_id` MUST be null.
  - All other levels (Site / Area / Unit / Component / Device)
    MUST have a non-null `parent_id`.

Eventual-consistency stance: the decider does NOT verify the
referenced parent Asset exists in the event store. Cycle
detection (target's ancestors must not include this asset)
requires walking the parent chain and is deferred to projection-
worker era. The single-parent tree rule is enforced structurally
(one `parent_id` field, can't be a list).

**Levels are conventional, not enforced**: the decider does NOT
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
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlreadyExistsError,
    AssetLevel,
    AssetName,
    AssetOwnerAlreadyPresentError,
    AssetRegistered,
    InvalidAssetParentError,
)
from cora.equipment.features.register_asset.command import RegisterAsset


def decide(
    state: Asset | None,
    command: RegisterAsset,
    *,
    now: datetime,
    new_id: UUID,
) -> list[AssetRegistered]:
    """Decide the events produced by registering a new asset.

    Invariants:
      - State must be None (genesis-only) -> AssetAlreadyExistsError
      - Name must be valid -> InvalidAssetNameError
        (via AssetName VO)
      - Enterprise-level Assets must have parent_id=None
        -> InvalidAssetParentError
      - Non-Enterprise-level Assets must have a non-null parent_id
        -> InvalidAssetParentError
      - Owner names must be unique within the payload (Lock 6)
        -> AssetOwnerAlreadyPresentError
    """
    if state is not None:
        raise AssetAlreadyExistsError(state.id)

    name = AssetName(command.name)  # validates + trims; raises InvalidAssetNameError

    # Hierarchy rule: Enterprise → null parent; others → required parent.
    if command.level is AssetLevel.ENTERPRISE and command.parent_id is not None:
        msg = f"Enterprise-level Asset cannot have a parent (got parent_id={command.parent_id})"
        raise InvalidAssetParentError(msg)
    if command.level is not AssetLevel.ENTERPRISE and command.parent_id is None:
        msg = (
            f"{command.level.value}-level Asset must have a parent "
            f"(parent_id=None is reserved for Enterprise roots)"
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
            level=command.level.value,
            parent_id=command.parent_id,
            occurred_at=now,
            drawing=command.drawing,
            model_id=command.model_id,
            alternate_identifiers=command.alternate_identifiers,
            owners=command.owners,
        )
    ]

"""Pure decider for the `RegisterAsset` command.

Pure function: given the current Asset state (None for a fresh
stream) and a `RegisterAsset` command, returns the events to
append. No I/O, no awaits, no side effects.

`now` and `new_id` are injected by the application handler from
the Clock and IdGenerator ports.

## Hierarchy rule

Per the BC map's hierarchy semantics:
  - `Enterprise` is the root level — `parent_id` MUST be null.
  - All other levels (Site / Area / Unit / Assembly / Device)
    MUST have a non-null `parent_id`.

Eventual-consistency stance: the decider does NOT verify the
referenced parent Asset exists in the event store. Cycle
detection (target's ancestors must not include this asset)
requires walking the parent chain and is deferred to projection-
worker era. The single-parent tree rule is enforced structurally
(one `parent_id` field, can't be a list).

**Levels are conventional, not enforced**: the decider does NOT
check that a Device's parent is an Assembly (etc). Device-in-
Device is allowed when reality demands it (smart instruments
with addressable sub-modules).

## Model binding (Lock B)

`command.model_id` flows through to the emitted AssetRegistered
event without inspection. The decider does NOT load the Model
snapshot: at registration the Asset's families set is empty, so
the cross-BC subset invariant
`Model.declared_families subset-of Asset.family_ids` is vacuously
satisfied and there is nothing to validate against. The handler
enforces Model existence (raises `ModelNotFoundError` -> 404)
before invoking decide; the first meaningful subset enforcement
fires at the first `add_asset_family` call against the bound
Asset.
"""

from datetime import datetime
from uuid import UUID

from cora.equipment.aggregates.asset import (
    Asset,
    AssetAlreadyExistsError,
    AssetLevel,
    AssetName,
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

    return [
        AssetRegistered(
            asset_id=new_id,
            name=name.value,
            level=command.level.value,
            parent_id=command.parent_id,
            occurred_at=now,
            drawing=command.drawing,
            model_id=command.model_id,
        )
    ]

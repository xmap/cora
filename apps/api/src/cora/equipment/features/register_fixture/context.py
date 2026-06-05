"""Context snapshot loaded by the register_fixture handler.

Single-stream-write + cross-aggregate-read pattern: the handler
loads the target Assembly state plus every referenced Asset state
BEFORE calling the decider, packs the results into this VO, and
hands it to the pure decider for invariant enforcement.

`assembly_state` is `None` when the assembly_id does not resolve
(decider raises `AssemblyNotFoundError`).

`family_ids_by_asset_id` maps each referenced asset_id to its
`family_ids` set, or `None` when the asset_id did not resolve.
A `None` value tells the decider to raise
`FixtureAssetNotFoundError` carrying the missing id
(sorted-first for deterministic responses).

`lifecycle_by_asset_id` maps each referenced asset_id to its current
`AssetLifecycle`, or `None` when the asset_id did not resolve. Used
by the decider to raise `FixtureAssetNotAttachableError` for
Decommissioned bindings (rejecting at register-time prevents the
operator from registering a Fixture that would inevitably fail
later at `attach_asset_to_fixture`, since Fixture is single-event-
genesis and cannot be amended). Empty dict (default) means no
lifecycle info was loaded; the decider skips the guard entirely
(useful for decider unit tests that exercise other invariants).
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.assembly import Assembly
from cora.equipment.aggregates.asset import AssetLifecycle


@dataclass(frozen=True)
class RegisterFixtureContext:
    """Snapshot of Assembly + Asset existence + lifecycle checks."""

    assembly_state: Assembly | None
    family_ids_by_asset_id: dict[UUID, frozenset[UUID] | None] = field(
        default_factory=dict[UUID, frozenset[UUID] | None]
    )
    lifecycle_by_asset_id: dict[UUID, AssetLifecycle | None] = field(
        default_factory=dict[UUID, AssetLifecycle | None]
    )

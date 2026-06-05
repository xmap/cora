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

`mount_id_by_asset_id` maps each referenced asset_id to the Mount
currently holding it (sourced from `proj_equipment_asset_location`),
or `None` when the Asset is not currently installed. The whole field
is `None` when the handler ran without a pool (test path) and the
orphan guard is disabled entirely; this matches the
install_asset / decommission_asset projection-precondition
short-circuit convention. When non-None and an entry maps to
`None`, the decider raises `FixtureAssetNotInstalledError` carrying
the sorted-first orphan id: a Fixture should snapshot only
equipment already on the floor, so install-then-register is
the contract.
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.assembly import Assembly
from cora.equipment.aggregates.asset import AssetLifecycle


@dataclass(frozen=True)
class RegisterFixtureContext:
    """Snapshot of Assembly + Asset existence + lifecycle + install checks."""

    assembly_state: Assembly | None
    family_ids_by_asset_id: dict[UUID, frozenset[UUID] | None] = field(
        default_factory=dict[UUID, frozenset[UUID] | None]
    )
    lifecycle_by_asset_id: dict[UUID, AssetLifecycle | None] = field(
        default_factory=dict[UUID, AssetLifecycle | None]
    )
    mount_id_by_asset_id: dict[UUID, UUID | None] | None = None

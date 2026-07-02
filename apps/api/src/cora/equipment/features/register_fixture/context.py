"""Context snapshot loaded by the register_fixture handler.

Single-stream-write + cross-aggregate-read pattern: the handler
loads the target Assembly state plus every referenced Asset state
BEFORE calling the decider, packs the results into this VO, and
hands it to the pure decider for invariant enforcement.

`assembly_state` is `None` when the assembly_id does not resolve
(decider raises `AssemblyNotFoundError`).

`sub_assembly_states` maps each child Assembly id referenced by the
top Assembly's `required_sub_assemblies` to its loaded state, or
`None` when it does not resolve (decider raises
`SubAssemblyNotFoundForAssemblyError`). The decider expands the union
of the top + sub leaf slots from these states.

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

`affordances_by_family_id` maps each bound Asset's Family id to that
Family's Affordance value strings (from `FamilyLookup`). Together with
`required_affordances_by_role_id` (each Role in the Assembly's
`presents_as`, from `RoleLookup`), the decider enforces the deferred
affordance-superset guarantee: the union of the bound Families'
affordances must cover every presented Role's `required_affordances`
(`FixtureCannotPresentRoleError`). Both default empty; when empty the
decider skips the check (the Assembly presents no Roles, or a
pool-less test path did not load the projections). Affordances are
typed `frozenset[str]` to match the cross-aggregate lookup ports.
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.equipment.aggregates.assembly import Assembly
from cora.equipment.aggregates.asset import AssetLifecycle


@dataclass(frozen=True)
class RegisterFixtureContext:
    """Snapshot of Assembly + Asset existence + lifecycle + install + affordance checks."""

    assembly_state: Assembly | None
    sub_assembly_states: dict[UUID, Assembly | None] = field(
        default_factory=dict[UUID, Assembly | None]
    )
    family_ids_by_asset_id: dict[UUID, frozenset[UUID] | None] = field(
        default_factory=dict[UUID, frozenset[UUID] | None]
    )
    lifecycle_by_asset_id: dict[UUID, AssetLifecycle | None] = field(
        default_factory=dict[UUID, AssetLifecycle | None]
    )
    mount_id_by_asset_id: dict[UUID, UUID | None] | None = None
    affordances_by_family_id: dict[UUID, frozenset[str]] = field(
        default_factory=dict[UUID, frozenset[str]]
    )
    required_affordances_by_role_id: dict[UUID, frozenset[str]] = field(
        default_factory=dict[UUID, frozenset[str]]
    )

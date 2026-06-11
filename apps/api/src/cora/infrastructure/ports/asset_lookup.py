"""AssetLookup port: cross-aggregate query for Equipment BC's Asset projection.

Used by cross-BC consumers that hold an `AssetId` from the wire and
need to validate the Asset exists (and optionally inspect its tier
or lifecycle) before committing a command. First consumer is the
Supply BC's `register_supply` handler (Session 5 Slice 7B): it
resolves `command.containing_asset_id` to an `AssetLookupResult` at
the handler port edge and threads the result into the decider as
`asset_lookup_result`. Future Slice 8 consumers (Asset.facility_id
back-binding) and potential Safety / Caution BC consumers will
also consume this port.

## Convention

This is a cross-aggregate port (Equipment BC ships the production
adapter `PostgresAssetLookup` reading `proj_equipment_asset_summary`;
multiple BC handlers consume it). Lives in
`cora.infrastructure.ports` per the existing pattern (`Authorize`,
`ClearanceLookup`, `CautionLookup`, `SupplyLookup`, `SecretStore`,
`CredentialLookup`, `FacilityLookup`).

The port is shaped around the CONSUMER's need: cross-BC binding sites
need "does this Asset exist and what's its identity + tier + lifecycle"
to validate before commit. The decommissioned-Asset binding question
is decided per-consumer at the decider boundary (slice 7B Supply
follows the slice 6A FacilityLookup precedent: bind anyway, the
operator chose to keep the lineage visible).

## Modern DDD alignment

Per Khononov / Cockburn / Herberto Graca: cross-aggregate integration
at command time should go through a port that the consumer shapes,
with the implementor providing the adapter. The replicated read
model (`proj_equipment_asset_summary`) is the modern recommendation
over synchronous replay of the Asset aggregate, because the
projection is already a denormalized cross-stream view + already
covers the hierarchy + lifecycle FSM.

## No BC imports in the port

`tier` and `lifecycle` are typed as `str` (not Equipment BC's
`AssetTier` / `AssetLifecycle` StrEnums) so this port stays inside
`cora.infrastructure`'s `depends_on = []` tach contract. The values
match the StrEnum string values; consumer deciders partition by
literal comparison (`tier == "Unit"`, `lifecycle == "Active"`) and
cast to typed enums at their boundary if they need the discipline.

`id` is typed `UUID` (Equipment BC's Asset.id is bare UUID, not a
NewType, so no cross-BC NewType to thread). Consumers that care
about the typed identity wrap at their BC boundary.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AssetLookupResult:
    """Summary row from `proj_equipment_asset_summary` for cross-aggregate checks.

    Carries the minimal columns cross-BC consumers need to validate
    cross-aggregate invariants before commit. Loaded by the handler
    via `AssetLookup.lookup` and handed to the decider in the slice's
    context object (mirrors `FacilityLookupResult` shape).

    `tier` and `lifecycle` are the StrEnum values as plain strings
    (matches the projection's `TEXT` columns); the consumer decider
    partitions on the literals it cares about.

    `name` is the operator-readable display name (1-200 chars per
    `AssetName` VO); useful for surfacing in cross-BC error messages
    that name the Asset operators recognize rather than a bare UUID.

    `family_affordances` is the union of the closed-enum Affordance
    value strings across every Family the Asset belongs to. Typed
    `frozenset[str]` (not `frozenset[Affordance]`) so this port stays
    inside `cora.infrastructure`'s `depends_on = []` tach contract,
    free of any Equipment BC import; consumer deciders compare against
    literal value strings (for example `"Capturing" in family_affordances`)
    and cast to the typed enum at their boundary if they need the
    discipline. Empty when the Asset belongs to no Family or none of
    its Families declare any affordance. The Data BC `record_acquisition`
    decider gates on `"Capturing"` membership; future cross-BC
    affordance-gated consumers read the same set.

    Future columns (parent_id, controller_id, facility_id post-7B,
    fixture_id) can be added additively as cross-BC consumers need
    them; the slice 6A `FacilityLookupResult.trust_anchor_credential_ids`
    extension is the precedent.
    """

    id: UUID
    name: str
    tier: str
    lifecycle: str
    family_affordances: frozenset[str]


class AssetLookup(Protocol):
    """Cross-aggregate port: query Equipment's Asset projection by id."""

    async def lookup(self, asset_id: UUID) -> AssetLookupResult | None:
        """Return the projection row for `asset_id`, or None if not found.

        Returning None signals "no Asset with that id is visible in
        the projection". Callers (`register_supply` containing-Asset
        validation today; future Slice 8 Asset.facility_id binding,
        future Safety / Caution BC consumers) translate None to the
        appropriate domain error at the decider boundary.

        Assets in EVERY lifecycle are returned (Commissioned, Active,
        Maintenance, Decommissioned); the decider partitions on
        `lifecycle` if it needs to distinguish "no Asset at all" from
        "Asset exists but Decommissioned". The slice 6A FacilityLookup
        precedent is to bind anyway and let the operator keep the
        lineage visible.
        """
        ...


__all__ = ["AssetLookup", "AssetLookupResult"]

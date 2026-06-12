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

ANCESTOR_WALK_DEPTH_CAP = 50
"""Maximum `parent_id` chain depth `ancestors_of` walks before failing.

Belt-and-braces against a runaway walk; the load-bearing cycle
terminator is the adapter mechanism (Postgres `CYCLE` clause / the
in-memory visited-set), this cap is the secondary ceiling. Set well
above any legitimate Equipment containment tree (today's 2-BM tree is
2 deep: Device -> Unit; even a future Device -> hutch -> Unit ->
sub-facility nesting stays in single digits). A walk that exceeds 50
levels is a cycle or data corruption, not a real tree, and raises
`AncestorWalkDepthExceededError`. Defined here (the walk contract's
home) and imported by exactly the two `AssetLookup` adapters; an arch
fitness test pins that single-definition-site discipline.
"""


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

    Snapshot columns whose purpose is a one-hop read (for example
    `controller_id`, `fixture_id`, `facility_code`) can be added
    additively as cross-BC consumers need them; the slice 6A
    `FacilityLookupResult.trust_anchor_credential_ids` extension is
    the precedent. Walk-axis fields go behind walk methods: a field
    whose purpose is to TRAVERSE a chain (notably `parent_id`) does
    NOT belong on this snapshot row. Parent-chain traversal is the
    `ancestors_of` method's job, which reads `parent_id` internally
    and returns these same snapshot rows, never exposing the
    traversal axis as a result field.
    """

    id: UUID
    name: str
    tier: str
    lifecycle: str
    family_affordances: frozenset[str]


class AncestorWalkDepthExceededError(Exception):
    """`ancestors_of` hit a parent_id cycle or exceeded the depth cap.

    Raised by every `AssetLookup` adapter's `ancestors_of` when the
    parent_id walk either revisits an Asset (a cycle such as A -> B ->
    A) or descends past `ANCESTOR_WALK_DEPTH_CAP` levels without
    reaching a root. The adapters NEVER truncate-and-return a partial
    closure: a partial ancestor set would silently under-scope the
    enclosure pre-flight gate (admitting a Run that an unreached
    ancestor's Enclosure should refuse), so the walk fails loud
    instead.

    The message names BOTH the observed depth and the cap so an
    operator can distinguish a legitimate-but-deep tree (raise the
    cap) from a genuine cycle (fix the parent_id). Cycle detection is
    defense-in-depth: the Asset write side does not yet enforce
    acyclicity, so the read-time walk must protect itself.
    """

    def __init__(self, *, observed_depth: int, cap: int) -> None:
        super().__init__(
            f"ancestors_of walk exceeded the depth cap (observed_depth="
            f"{observed_depth}, cap={cap}): a parent_id cycle or a tree "
            f"deeper than the cap. Fix the cycle, or raise "
            f"ANCESTOR_WALK_DEPTH_CAP if the depth is legitimate."
        )
        self.observed_depth = observed_depth
        self.cap = cap


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

    async def ancestors_of(self, asset_ids: frozenset[UUID]) -> frozenset[AssetLookupResult]:
        """Return the ancestor closure of `asset_ids` (inclusive).

        Walks each Asset's `parent_id` chain upward and returns the
        union of the input Assets plus every ancestor, as
        `AssetLookupResult` rows (the same snapshot shape `lookup`
        returns, so consumers partition on `lifecycle` the same way).
        The input ids are included in the result; an input id with no
        projection row contributes nothing (no row exists to walk
        from).

        Termination: the walk stops at any Asset whose `parent_id IS
        NULL` (a facility-rooted root Asset, the post-AssetLevel-
        collapse anchoring where a root binds `facility_code` and has
        no Asset parent) and NEVER reads the Federation `Facility`
        aggregate. The two structural-scope axes (Equipment
        `Asset.parent_id`, Federation `Facility.parent_id`) are joined
        by `Asset.facility_code`, never traversed together here.

        Cycle / runaway defense: a `parent_id` cycle (A -> B -> A) or
        a chain deeper than `ANCESTOR_WALK_DEPTH_CAP` raises
        `AncestorWalkDepthExceededError` rather than looping or
        silently truncating the closure. Empty input returns the
        empty frozenset without touching any store.

        The signature is flat positional by design: no keyword-only
        filter / depth / edge-type parameters. A federation-spanning
        walk that crosses into the Facility axis is a SEPARATE sibling
        method (`ancestors_of_across_facilities`), not a parameter
        here; the down-chain mirror is a separate `descendants_of`
        method, each landing only when its own consumer trigger fires.
        """
        ...


__all__ = [
    "ANCESTOR_WALK_DEPTH_CAP",
    "AncestorWalkDepthExceededError",
    "AssetLookup",
    "AssetLookupResult",
]

"""SupplyLookup port: cross-BC query for Supply BC's status projection.

Used by Run BC's `start_run` handler and Operation BC's
`start_procedure` handler to gate Run / Procedure start on the
presence of at least one AVAILABLE Supply for every kind that the
governing Method declared in its `needed_supplies` field.

## Convention

Third cross-BC port (after `Authorize` and `ClearanceLookup`,
mirrored by `CautionLookup`): one implementor (Supply BC ships
`PostgresSupplyLookup` reading `proj_supply_summary`), multiple
consumers (Run today; Operation alongside). Lives in
`cora.infrastructure.ports` per the existing pattern. Shaped around
the consumer's need (the start-time gate needs "which Supplies of
each requested kind are registered, and in what status?"); the
adapter translates Supply BC's projection columns to this shape.

## Available-only semantics

The decider, not this port, gates on `status == SupplyStatus.AVAILABLE`.
The port returns every matching Supply regardless of status so the
decider can produce a useful diagnostic ("LiquidNitrogen has a
Supply but it's Unavailable") distinct from absence ("no LN2 Supply
registered at all"). Decommissioned rows are filtered at the query
layer per [[project_deregister_supply_design]] (tombstones should
not count toward gate satisfaction). See
[[project_supply_preflight_gate_design]] for the shared decision.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class SupplyLookupResult:
    """Summary row from `proj_supply_summary` for cross-BC consumers.

    Carries the minimal columns the cross-BC consumers (Run / Operation
    pre-flight gate; Data BC register_distribution; future Trust BC
    credential rotation) need to make their decisions and produce
    diagnostics. Loaded by the handler via
    `SupplyLookup.find_supplies_by_kind` (grouped query) or
    `SupplyLookup.lookup` (single-id query) and handed to the
    consumer's decider.

    `status` is the StrEnum value as a plain string (matches the
    projection's `TEXT` column); consumers treat it opaquely and
    partition on `"Available"` (pre-flight gate) or pass it through
    (register_distribution status-agnostic bind).

    `kind` is the bare-str Supply.kind value (today; future closed-StrEnum
    move per Supply BC's own roadmap). Distribution's register decider
    gates on `kind == "Storage"`.

    `facility_code` carries the resolved Facility code of the Supply's
    owning Facility (added for the Data BC register_distribution
    consumer + future federation use cases). Bare str on the wire per
    [[project-facility-aggregate-design]] convention.

    `supply_id` is typed `UUID` for cross-port symmetry with
    `ClearanceLookupResult.clearance_id` and `CautionLookupResult.caution_id`.
    """

    supply_id: UUID
    kind: str
    name: str
    status: str
    facility_code: str


class SupplyLookup(Protocol):
    """Cross-BC port: query Supply's status projection from Run + Operation + Data BCs."""

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyLookupResult]]:
        """Return Supplies grouped by kind for every requested kind.

        The returned mapping is keyed by kind string and contains
        ONLY the kinds for which at least one non-Decommissioned
        Supply is registered. Kinds with no registered Supply are
        absent from the mapping (the decider treats absence as a
        missing-kind rejection distinct from a no-Available
        rejection).

        Decommissioned Supplies are filtered out at the query layer:
        tombstones do not count toward satisfaction. Operators who
        deregister a typo-Supply do not see that row contributing to
        a satisfied gate.

        Empty input (`kinds = frozenset()`) returns an empty
        mapping; the handler should short-circuit before calling the
        port for Methods with no `needed_supplies`.
        """
        ...

    async def lookup(self, supply_id: UUID) -> SupplyLookupResult | None:
        """Return the projection row for `supply_id`, or `None` if not found.

        Consumers needing to validate a specific supply (the Data BC
        register_distribution handler being the first such consumer)
        use this single-id query in preference to the grouped
        find_supplies_by_kind interface.

        Supplies in EVERY status are returned (Available, Degraded,
        Unavailable, Recovering, Decommissioned); the consumer
        decider partitions on `status` if it needs to distinguish
        "no Supply at all" from "Supply exists but in non-Available
        state". register_distribution intentionally accepts every
        status because a Distribution can legitimately be registered
        against a Decommissioned Supply for archival completeness;
        only `kind` is gated.

        Mirrors `AssetLookup.lookup` shape one-for-one for cross-port
        symmetry.
        """
        ...


class AllSatisfiedSupplyLookup:
    """Test-default stub: returns ONE synthetic Available Supply per requested kind.

    Mirrors `AlwaysCoveredClearanceLookup`'s role for `ClearanceLookup`:
    tests that don't care about the Supply gate get this stub from
    `build_postgres_deps` defaults, so existing Run / Procedure tests
    don't have to seed real Supplies. Tests that exercise the gate
    explicitly override with the real adapter (`PostgresSupplyLookup`)
    and seed Supplies via `register_supply` + `mark_supply_available`.

    The synthetic Supply has `status="Available"` so every kind
    requested by Method.needed_supplies satisfies the decider's
    gate. Tests that need to assert the missing-kind or no-Available
    rejection paths MUST use the real `PostgresSupplyLookup`
    adapter, not this stub.

    `lookup(supply_id)` returns `None` by default; tests that exercise
    Distribution's register flow against this stub will see the
    `DistributionSupplyNotFoundError` rejection path, which is the
    correct conservative default for a not-explicitly-seeded stub.
    """

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyLookupResult]]:
        from cora.infrastructure.routing import NIL_SENTINEL_ID

        return {
            kind: [
                SupplyLookupResult(
                    supply_id=NIL_SENTINEL_ID,
                    kind=kind,
                    name=f"<test stub: {kind}>",
                    status="Available",
                    facility_code="<test stub facility>",
                )
            ]
            for kind in kinds
        }

    async def lookup(self, supply_id: UUID) -> SupplyLookupResult | None:
        _ = supply_id
        return None


class NoSuppliesRegisteredLookup:
    """Test stub: returns an empty mapping for any input.

    Use when a test needs to exercise the missing-kind rejection
    path without seeding any real Supplies (decider raises
    `RunRequiresAvailableSupplyError` or
    `ProcedureRequiresAvailableSupplyError` for every kind in
    `Method.needed_supplies`).

    `lookup(supply_id)` returns `None` (no Supplies registered at all
    means every per-id lookup is a miss).
    """

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyLookupResult]]:
        _ = kinds
        return {}

    async def lookup(self, supply_id: UUID) -> SupplyLookupResult | None:
        _ = supply_id
        return None


class UnknownSupplyLookup:
    """Test stub: `lookup(supply_id)` always returns `None`.

    Mirrors `AllSatisfiedSupplyLookup` / `NoSuppliesRegisteredLookup`
    shape but specifically supports the Distribution register flow's
    "Supply lookup returned None" branch. The grouped
    `find_supplies_by_kind` interface returns an empty mapping
    (tests using this stub do not exercise the pre-flight gate; if
    they do, see `AllSatisfiedSupplyLookup`).
    """

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyLookupResult]]:
        _ = kinds
        return {}

    async def lookup(self, supply_id: UUID) -> SupplyLookupResult | None:
        _ = supply_id
        return None


class SingleSupplyLookup:
    """Test stub: `lookup(supply_id)` returns ONE configured Supply.

    Use when a Distribution-register test needs to exercise the
    happy path (or specific kind/status branches) without spinning
    up the real `PostgresSupplyLookup` adapter. Construct with a
    fixed `SupplyLookupResult`; every `lookup` call returns the same
    reference. `find_supplies_by_kind` returns empty (out of scope).
    """

    def __init__(self, reference: SupplyLookupResult) -> None:
        self._reference = reference

    async def find_supplies_by_kind(
        self,
        *,
        kinds: frozenset[str],
    ) -> Mapping[str, list[SupplyLookupResult]]:
        _ = kinds
        return {}

    async def lookup(self, supply_id: UUID) -> SupplyLookupResult | None:
        if supply_id == self._reference.supply_id:
            return self._reference
        return None

"""CapabilityLookup port: cross-BC query for Recipe's Capability projection.

Used by Equipment BC's `get_asset_integration_view` handler to surface
the set of Recipe Capabilities whose `required_affordances` are covered
by an Asset's combined Family affordances. The result feeds the
`applicable_capabilities` field of the read-time integration bundle.

## Convention

The fourth cross-BC lookup port (after `ClearanceLookup`,
`CautionLookup`, `SupplyLookup`): one implementor (Recipe BC ships
`PostgresCapabilityLookup` reading `proj_recipe_capability_summary`),
one consumer today (Equipment), shape determined by the consumer's
need. Lives in `cora.infrastructure.ports` per the existing pattern.

The port shape is `find_applicable_by_affordances(affordances) ->
list[CapabilityLookupResult]`. Filter is affordance-set containment
(`required_affordances <@ affordances`) plus status in
`{Defined, Versioned}` (Deprecated capabilities are excluded). This
mirrors the read predicate Equipment used to inline as raw SQL
before the port was extracted.

## Discipline

Family's docstring at `cora.equipment.aggregates.family.state`
reserves the word "Capability" for Recipe BC. The port lets Equipment
ask Recipe a question through a Protocol whose name uses Recipe's
vocabulary, without Equipment's domain code learning the word. The
handler maps `CapabilityLookupResult` to Equipment's local
`CapabilityView` response type.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class CapabilityLookupResult:
    """Summary row from `proj_recipe_capability_summary` returned to consumers.

    Carries the minimal columns the integration-view handler needs to
    map onto its public `CapabilityView` response shape. Adding fields
    to this dataclass is a port-version bump that touches the adapter
    plus every consumer.
    """

    capability_id: UUID
    code: str
    name: str
    status: str  # "Defined" | "Versioned"


class CapabilityLookup(Protocol):
    """Cross-BC port: query Recipe's Capability projection from Equipment."""

    async def find_applicable_by_affordances(
        self,
        affordances: frozenset[str],
    ) -> list[CapabilityLookupResult]:
        """Return every non-Deprecated Capability whose required_affordances are covered.

        "Covered" means `required_affordances <@ affordances` (every
        affordance the Capability requires is present in the passed
        set). Empty `affordances` yields only Capabilities with empty
        `required_affordances`. Status filter excludes Deprecated.

        Results are sorted by `code` ascending for deterministic
        downstream serialization.
        """
        ...


class AlwaysEmptyCapabilityLookup:
    """Test-default stub: returns `[]`.

    Mirrors `AlwaysQuietCautionLookup` and `AlwaysCoveredClearanceLookup`:
    tests that do not exercise applicable-capability semantics get
    this stub from kernel-construction defaults, so existing Equipment
    tests do not have to seed Capability projection rows. Tests that
    do exercise the surface override with a fake returning seeded
    references, or with the real `PostgresCapabilityLookup` against
    a testcontainers pool.
    """

    async def find_applicable_by_affordances(
        self,
        affordances: frozenset[str],
    ) -> list[CapabilityLookupResult]:
        _ = affordances
        return []

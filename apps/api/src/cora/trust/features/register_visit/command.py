"""The `RegisterVisit` command -- intent dataclass for this slice.

Genesis command. Caller-supplied `visit_id` so a BSS subscriber can
mint deterministic UUIDs (`uuid5(NAMESPACE_BSS, f'{scheme}:{external_id}')`)
for replay-safe ingest, while operator-direct registration can also supply
a UUID.

`parent_id` and `external_refs` ship on the command alongside
the lifecycle fields to avoid a two-pass event-payload migration when
the partOf cohesion check + external-ref query slices land.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from cora.shared.identifier import Identifier
from cora.trust.aggregates.visit import VisitType


@dataclass(frozen=True)
class RegisterVisit:
    """Register a new Visit on a Surface under a Policy.

    `policy_id`: REQUIRED -- the authz envelope. Visit references the
    same Policy that Trust's Authorize port gates commands against, so
    a single source of truth answers "is this actor allowed to act in
    this Visit's context".

    `surface_id`: REQUIRED -- Visit is Surface-scoped (not Policy-
    scoped). One Policy may host many Visits across Surfaces (S8
    multi-instrument case).

    `type`: REQUIRED closed enum classifying the operational nature.
    Replaces sentinel-value anti-pattern (no `gup=0` magic).

    `planned_start_at` + `planned_end_at`: REQUIRED. Decider enforces
    `planned_end_at > planned_start_at`.

    `parent_id`: OPTIONAL self-FK for nested commissioning.

    `external_refs`: OPTIONAL anti-corruption refs to upstream-
    deferred concepts.
    """

    visit_id: UUID
    policy_id: UUID
    surface_id: UUID
    type: VisitType
    planned_start_at: datetime
    planned_end_at: datetime
    parent_id: UUID | None = None
    external_refs: frozenset[Identifier] = field(default_factory=frozenset[Identifier])

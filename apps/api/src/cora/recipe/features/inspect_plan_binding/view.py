"""Read-side view types for the `inspect_plan_binding` slice.

These are the shapes the handler returns. The route + MCP tool
adapt them to wire-friendly Pydantic models with primitive types.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from cora.equipment.aggregates.asset import AssetCondition, AssetLifecycle
from cora.equipment.aggregates.family import Affordance


class BindingStatus(StrEnum):
    """At-a-glance verdict for a candidate Plan binding.

    Computed from the loaded state. `MISSING_CAPABILITY` means the bound
    Method has no `capability_id` (legacy shape); the affordance
    guard is skipped per the `define_plan` decider's existing
    behaviour. When BOTH families and affordances are missing,
    status reports `MISSING_FAMILIES` (the primitive check that
    runs first in the decider); both detailed sets remain visible
    in the view so the operator sees the whole picture.
    """

    SATISFIED = "Satisfied"
    MISSING_FAMILIES = "MissingFamilies"
    MISSING_AFFORDANCES = "MissingAffordances"
    MISSING_CAPABILITY = "MissingCapability"


@dataclass(frozen=True)
class WiredAsset:
    """Per-wired-Asset contribution to the binding diagnostic.

    `condition` and `lifecycle` are the Asset's current health +
    lifecycle state at preview time. `family_ids` is the Asset's
    bound Family set. `contributed_affordances` is the union of
    affordances declared by those Families.

    `condition` is None for a virtual axis (an Asset carrying a
    `partition_rule`): a virtual axis has no hardware that can be
    Degraded or Faulted, so reporting `Nominal` for it would be
    misleading. The condition of its constituent motors is what
    matters, and those appear as their own wired Assets. Mirrors
    the virtual-axis self-gate in `get_asset_pidinst`.
    """

    asset_id: UUID
    asset_name: str
    condition: AssetCondition | None
    lifecycle: AssetLifecycle
    family_ids: frozenset[UUID]
    contributed_affordances: frozenset[Affordance]


@dataclass(frozen=True)
class CandidateAsset:
    """Per-Asset candidate for a missing affordance.

    Same shape as `WiredAsset` minus the all-affordances
    contribution. `contributing_family_ids` is deliberately named
    to differ from `WiredAsset.family_ids`: it holds ONLY
    the candidate's Families that declare the missing affordance
    under consideration, not the candidate's full Family set. The
    narrowing surfaces why the Asset is a candidate at all without
    forcing the operator to cross-reference Family.affordances
    themselves; the field name signals the difference so a naive
    union of wired-asset and candidate Family ids doesn't produce
    a misleading aggregate. Other state (condition, lifecycle) is
    unfiltered so the operator can see Decommissioned/Faulted
    candidates and decide whether to swap. `condition` is None for a
    virtual-axis candidate, same reason as `WiredAsset.condition`.
    """

    asset_id: UUID
    asset_name: str
    condition: AssetCondition | None
    lifecycle: AssetLifecycle
    contributing_family_ids: frozenset[UUID]


@dataclass(frozen=True)
class MissingAffordanceCandidates:
    """Per-missing-affordance group of facility-wide candidate Assets.

    `affordance` is one of the entries in the view's
    `missing_affordances` set. `candidates` is the set of Assets in
    the facility (excluding already-wired Assets) whose Family set
    contains a Family that declares this affordance. Sorted by
    asset_id string form for deterministic ordering.

    Empty `candidates` tuple means "we looked, found nothing": the
    facility has no Asset that could cover this affordance. The
    affordance still appears so the operator can see it was queried.
    """

    affordance: Affordance
    candidates: tuple[CandidateAsset, ...]


@dataclass(frozen=True)
class InspectPlanBindingView:
    """Full binding diagnostic returned by the handler.

    Always populates both `missing_family_ids` and `missing_affordances`
    so the operator sees the whole picture in one read, even when
    the decider would short-circuit on the family check. Empty
    frozensets mean that dimension is satisfied.

    `capability_id` is None when the Method has no Capability
    template (legacy shape); `capability_required_affordances` is
    empty in that case, and `binding_status` reports
    `MISSING_CAPABILITY`.

    `wired_assets` is sorted by asset_id string form for
    deterministic ordering across replays.

    `missing_affordance_candidates` is the per-missing-affordance
    enumeration of facility Assets that COULD cover the requirement.
    Empty tuple when no affordances are missing, OR when the handler
    runs without a configured pool (in-memory test mode): the
    candidate lookup is projection-backed and skipped gracefully.
    Sorted by affordance value for deterministic ordering.
    """

    practice_id: UUID
    method_id: UUID
    capability_id: UUID | None
    method_needed_family_ids: frozenset[UUID]
    capability_required_affordances: frozenset[Affordance]
    wired_assets: tuple[WiredAsset, ...]
    missing_family_ids: frozenset[UUID]
    missing_affordances: frozenset[Affordance]
    missing_affordance_candidates: tuple[MissingAffordanceCandidates, ...]
    binding_status: BindingStatus

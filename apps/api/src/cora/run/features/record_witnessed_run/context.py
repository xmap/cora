"""Cross-aggregate context the `record_witnessed_run` decider validates against.

`RunWitnessedStartContext` is the witnessed-genesis counterpart to `RunStartContext`
(`cora.run.features.start_run.context`). Deliberately a separate,
slice-local dataclass rather than a shared import: cross-slice sharing
through a feature module is banned (cross-slice independence), and the
two contexts are not identical shapes anyway (this one carries no
`campaign`, `input_distributions`, or `reachable_storage_supply_ids`,
since RunTranslator has no operator inputs in those axes).

## Field semantics

Same loading and gating semantics as the matching `RunStartContext`
fields, with one difference: `referencing_enclosures` and
`beam_availability` are still LOADED here exactly as at a driven start,
but the decider WITNESSES them (via `witness_safety_envelope`) instead of
enforcing them. `referencing_clearances` and `needed_supplies_satisfaction`
are still ENFORCED (via the same `clearance_gate_check` /
`supply_gate_check` functions the driven decider uses), per the roadmap's
rule: CORA-side data faults stay refusals on both paths.

  - `plan`: the Plan being executed. Decider rejects if Deprecated.
  - `subject`: the Subject being measured, or None (the common case for
    a watched capture today). Decider rejects if non-None and not in
    Mounted | Measured.
  - `assets`: dict keyed by asset_id, loaded from `plan.asset_ids`.
    Decider rejects if any is Decommissioned, and re-validates capability
    superset against current Asset state.
  - `referencing_clearances`: every Safety clearance whose bindings
    reference this Run's scope, loaded exactly as at a driven start.
    Still gates: a witnessed genesis without an Active Clearance still
    refuses.
  - `active_cautions`: every Active Caution in scope. Non-blocking,
    embedded on `RunStarted.acknowledged_cautions` exactly as at a
    driven start.
  - `needed_supplies_satisfaction`: mapping keyed by Supply kind. Still
    gates: a witnessed genesis without an Available Supply of a required
    kind still refuses.
  - `referencing_enclosures`: every Enclosure the Run's scoped Assets (or
    ancestors) declare via `located_in_enclosure_id`. WITNESSED, not
    enforced: a NotPermitted enclosure records `enclosure_permitted=False`
    on the emitted verdict rather than refusing the genesis.
  - `beam_availability`: the live beam reading, or None when the
    deployment configures no beam PVs. WITNESSED, not enforced, same
    reason as `referencing_enclosures`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

from cora.equipment.aggregates.asset import Asset
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.ports.caution_lookup import CautionLookupResult
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.recipe.aggregates.plan import Plan
from cora.subject.aggregates.subject import Subject


@dataclass(frozen=True)
class RunWitnessedStartContext:
    """Snapshot of upstream aggregate state at a witnessed Run's genesis."""

    plan: Plan
    subject: Subject | None
    assets: dict[UUID, Asset]
    referencing_clearances: tuple[ClearanceLookupResult, ...]
    active_cautions: tuple[CautionLookupResult, ...] = ()
    needed_supplies_satisfaction: Mapping[str, tuple[SupplyLookupResult, ...]] = field(
        default_factory=lambda: cast("Mapping[str, tuple[SupplyLookupResult, ...]]", {})
    )
    referencing_enclosures: tuple[EnclosureLookupResult, ...] = ()
    beam_availability: BeamAvailabilityLookupResult | None = None

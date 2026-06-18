"""Cross-aggregate context the `start_run` decider validates against.

`RunStartContext` is built by the `start_run` handler from
`load_plan` + `load_subject` (if subject_id given) + `load_asset`
calls before reaching the pure decider. The decider treats these
loaded entities as opaque domain data and validates the Run-start
preconditions without performing any I/O.

Per gate-review Q2 / Q5: this is the canonical pattern for cross-
aggregate validation in CORA, mirroring `PlanBindingContext` from
6e-1 (the first decider that took cross-aggregate state as input).
Documented in CONTRIBUTING.md as the cross-aggregate-validation
idiom for any future cross-validating decider.

Slice-local module by design: only `start_run` uses it today.

## Field semantics

  - `plan`: the Plan being executed. Decider rejects if Deprecated.
  - `subject`: the Subject being measured, or None for dark-field /
    flat-field calibration runs (per beamline-domain convention).
    Decider rejects if non-None and not in Mounted | Measured.
  - `assets`: dict keyed by asset_id, loaded from `plan.asset_ids`.
    Decider rejects if any is Decommissioned, and re-validates
    capability superset against current Asset state (drift since
    Plan-bind is real; Run is the last gate).
  - `referencing_clearances`: every Safety clearance
    whose bindings reference this Run's scope (run_id, subject_id,
    asset_ids), regardless of status. Loaded by the handler via
    `deps.clearance_lookup.find_referencing_run(...)` against the
    `proj_safety_clearance_summary` projection. Decider partitions
    on `status == "Active"` to distinguish "no clearance at all"
    (`RunRequiresActiveClearanceError`) from "clearance exists but
    none Active" (`RunClearanceCoverageMismatchError`).
  - `active_cautions`: every Active Caution whose
    target references the Run's scope (asset_ids + a future
    procedure_ids when a procedure-driven run shape lands). Loaded
    by the handler via
    `deps.caution_lookup.find_active_for_run(...)` against the
    `proj_caution_summary` projection. NON-BLOCKING by construction:
    the decider does NOT partition on this field; it only threads
    the snapshot into the `RunStarted` event payload as
    `acknowledged_cautions`. Distinct from
    `referencing_clearances` which IS a gate.

Naming: `assets` (not `bound_assets`) matches `PlanBindingContext`
precedent. The "bound" qualifier was meaningful at Plan-bind time
(Plan was doing the binding); at Run-start, Run isn't binding
anything new.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

from cora.campaign.aggregates.campaign import Campaign
from cora.equipment.aggregates.asset import Asset
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.ports.caution_lookup import CautionLookupResult
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.recipe.aggregates.plan import Plan
from cora.subject.aggregates.subject import Subject


@dataclass(frozen=True)
class RunStartContext:
    """Snapshot of upstream aggregate state at Run-start time.

    `subject` is None when the Run has no Subject (calibration /
    dark-field run). `assets` is loaded from `plan.asset_ids`.
    `referencing_clearances` carries every Safety clearance that
    references the Run's scope (Run/Subject/Asset bindings) at any
    status; the decider applies the Active-coverage check.
    `active_cautions` carries every Active Caution attached to the
    Run's scope; the decider does NOT gate on this field, only
    embeds it on the `RunStarted` event payload.

    `needed_supplies_satisfaction` is a mapping keyed by `Supply.kind`
    string carrying every non-Decommissioned Supply of each required
    kind from the governing Method's `needed_supplies` (loaded by the
    handler via `deps.supply_lookup.find_supplies_by_kind`). The
    decider gates on at-least-one-AVAILABLE per required kind per
    [[project_supply_preflight_gate_design]]: kinds absent from the
    mapping raise `RunRequiresAvailableSupplyError`; kinds present
    but with no Available entry raise `RunSupplyCoverageMismatchError`.
    Empty mapping is the natural state for Methods with empty
    `needed_supplies` (the handler skips the lookup).

    `campaign` is None unless `StartRun.campaign_id` was
    provided. When non-None the decider gates on `campaign.status`
    being in `{Planned, Active, Held}` (else
    `RunCannotJoinCampaignError`) and embeds the campaign_id on the
    `RunStarted` event payload. The handler additionally writes the
    inverse `CampaignRunAdded` event to the Campaign stream atomically
    via `EventStore.append_streams`.
    """

    plan: Plan
    subject: Subject | None
    assets: dict[UUID, Asset]
    referencing_clearances: tuple[ClearanceLookupResult, ...]
    active_cautions: tuple[CautionLookupResult, ...] = ()
    needed_supplies_satisfaction: Mapping[str, tuple[SupplyLookupResult, ...]] = field(
        default_factory=lambda: cast("Mapping[str, tuple[SupplyLookupResult, ...]]", {})
    )
    referencing_enclosures: tuple[EnclosureLookupResult, ...] = ()
    """Every Active Enclosure that any of the Run's scoped Assets (or
    their ancestors) declares as its `located_in_enclosure_id`. The
    handler walks the Asset ancestor closure
    (`deps.asset_lookup.ancestors_of`), collects the distinct
    `located_in_enclosure_id` across those rows, and loads their permit
    status via `deps.enclosure_lookup.find_by_ids(enclosure_ids=...)`.

    Empty tuple is Permit-by-default per the EnclosureLookup port
    docstring: an Asset located in no Enclosure has no enclosure-
    permit gate. The decider partitions each row on
    `permit_status == "Permitted" AND lifecycle == "Active"`;
    failing rows raise the appropriate cross-BC enclosure error per
    [[project_enclosure_stage1_design]] L-pre-1 (always-derive-from-
    Asset-chain). Methods do NOT declare a `needed_enclosure_permits`
    field; the located-in chain IS the declaration."""
    campaign: Campaign | None = None
    beam_availability: BeamAvailabilityLookupResult | None = None
    """Live beam-availability reading at the Run-start instant (BEAM-1),
    or None when the deployment configured no beam PVs (gate skipped,
    beam-by-default). The handler calls
    `deps.beam_availability_lookup.read_beam_availability()` and threads
    the result here; the decider gates on it (fail-closed when
    `quality_ok` is False; refuse when any of `fes_open` / `sbs_open` /
    `fes_permit` is False). The reading is consumed only by the gate and
    is intentionally NOT persisted on `RunStarted` (a started Run always
    passed the gate, so a stored snapshot would be all-open). Distinct
    axis from the Enclosure SecureM permit: beam-open is per-scan, the
    enclosure permit is access-state."""

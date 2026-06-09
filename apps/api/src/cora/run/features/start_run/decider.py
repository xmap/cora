"""Pure decider for the `StartRun` command.

Cross-aggregate validation: this is the second decider in the
codebase that takes upstream aggregate state as input (after Plan's
`define_plan`). Per gate-review Q2, the handler pre-loads
Plan + Subject (if subject_id given) + each bound Asset, hands the
loaded entities to this decider as a `RunStartContext`. The decider
treats them as opaque domain data and validates without any I/O.
`now` and `new_id` are injected by the handler from Clock and
IdGenerator ports.

This pattern is the canonical approach for cross-aggregate
validation in CORA going forward (Plan was first, Run is second).
Documented in CONTRIBUTING.md alongside the eventual-consistency
rule.

## Validation order

The decider runs validations in this order; each failure short-
circuits and raises immediately. Order chosen so the most
fundamental issues surface first:

1. State must be None (defensive: stream collision).
   `RunAlreadyExistsError`.
2. Plan must not be Deprecated → `RunBoundPlanDeprecatedError`.
3. Subject (if non-None) must be in {Mounted, Measured} →
   `RunSubjectNotMountableError`. Skipped entirely for calibration /
   dark-field runs (where command.subject_id is None and
   context.subject is None).
4. No bound Asset may be Decommissioned → `RunPlanAssetDecommissionedError`
   carrying the offending asset_ids.
5. RE-VALIDATE: `union(asset.family_ids) ⊇ method.needed_family_ids`
   against CURRENT Asset state (gate-review Q5: drift since Plan-bind
   is real; Run-start is the last gate before execution).
   `RunCapabilitiesNotSatisfiedError` carrying the missing capability
   ids. **NOTE**: Method's needed_family_ids comes via Plan; we
   load Plan but NOT Method here — instead, the handler resolved
   Plan → Method at load time and passes the needs as part of...
   wait, re-reading: actually we don't have Method directly in
   RunStartContext. Plan's bind-time snapshot in PlanDefined event
   carries `method_needed_family_ids_snapshot`, but we need
   CURRENT Method state for re-validation. The handler must load
   Method via plan.practice_id → practice.method_id → Method.
   See handler docstring.

   Wait, simpler: we re-load via the snapshot. The PlanDefined
   event captured method_id and the needs snapshot. We could trust
   the snapshot, OR we could re-load Method to get current
   needed_family_ids. Per gate-review Q5 ("re-validate at Run-
   start"), we re-load to catch Method drift too.

   Actually for 6f-1 simplicity, we trust Plan's bind-time
   snapshot for the needs side AND re-validate against current
   Asset capabilities. Method drift between bind and start is a
   secondary concern; if Method's needs change, operators should
   re-bind the Plan. Documented as known gap.

6. Name validation (via `RunName` VO). `InvalidRunNameError`. Last
   because the name is a primitive the operator can fix without
   changing any binding state.

## What's NOT validated

  - Decision approval (Decision BC not shipped). Documented as
    gate-review Q3 known gap.
  - Subject hazard ⊆ Method clearances (Method's hazardClearances
    facet not shipped). Documented as 6c-deferred enrichment.

## Supply pre-flight gate

For every kind in Method.needed_supplies, the decider requires at
least one Supply of that kind to be registered AND at least one of
them in status=Available. Default-strict: Degraded does NOT pass.
See [[project_supply_preflight_gate_design]] for the shared
"Available enough" lock; the handler loads the satisfaction map via
deps.supply_lookup.find_supplies_by_kind and threads it on
context.needed_supplies_satisfaction.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.campaign.aggregates.campaign import CampaignStatus
from cora.campaign.aggregates.campaign.events import CampaignRunAdded
from cora.equipment.aggregates.asset import AssetLifecycle
from cora.recipe.aggregates.plan import PlanStatus, validate_wire_endpoints
from cora.run.aggregates.run import (
    CautionAcknowledgement,
    Run,
    RunAlreadyExistsError,
    RunBoundPlanDeprecatedError,
    RunCannotJoinCampaignError,
    RunCapabilitiesNotSatisfiedError,
    RunClearanceCoverageMismatchError,
    RunEnclosureCoverageMismatchError,
    RunName,
    RunPlanAssetDecommissionedError,
    RunRequiresActiveClearanceError,
    RunRequiresAvailableSupplyError,
    RunRequiresPermittedEnclosureError,
    RunStarted,
    RunSubjectNotMountableError,
    RunSupplyCoverageMismatchError,
    validate_effective_parameters_against_method_schema,
    validate_pinned_calibration_ids,
)
from cora.run.features.start_run.command import StartRun
from cora.run.features.start_run.context import RunStartContext
from cora.subject.aggregates.subject import SubjectStatus

_SUBJECT_RUNNABLE_STATUSES: tuple[SubjectStatus, ...] = (
    SubjectStatus.MOUNTED,
    SubjectStatus.MEASURED,
)

_CAMPAIGN_MEMBERSHIP_ELIGIBLE_STATUSES: tuple[CampaignStatus, ...] = (
    CampaignStatus.PLANNED,
    CampaignStatus.ACTIVE,
    CampaignStatus.HELD,
)


@dataclass(frozen=True)
class RunStartEvents:
    """The events emitted by a successful `start_run` decision.

    Run-side `run_events` is always non-empty (one `RunStarted`).
    Campaign-side `campaign_events` is non-empty only when the command
    supplied `campaign_id`: a single `CampaignRunAdded` mirrors the
    membership write the handler hands to `EventStore.append_streams`.
    Empty otherwise; the handler routes single-stream via `append`.

    Mirrors `amend_clearance`'s `AmendmentEvents`: the decider owns
    cross-aggregate event construction (FCIS), the handler owns I/O
    routing.
    """

    run_events: list[RunStarted]
    campaign_events: list[CampaignRunAdded]


def decide(
    state: Run | None,
    command: StartRun,
    *,
    context: RunStartContext,
    needed_family_ids_snapshot: frozenset[UUID],
    needed_supplies_snapshot: frozenset[str] = frozenset(),
    effective_parameters: dict[str, Any],
    method_parameters_schema: dict[str, Any] | None,
    now: datetime,
    new_id: UUID,
) -> RunStartEvents:
    """Decide the events produced by starting a new run.

    Invariants:
      - State must be None (genesis-only) -> RunAlreadyExistsError
      - At least one Clearance must reference this Run's scope
        -> RunRequiresActiveClearanceError
      - At least one referencing Clearance must be Active
        -> RunClearanceCoverageMismatchError
      - Every kind in Method.needed_supplies must have at least
        one registered Supply -> RunRequiresAvailableSupplyError
      - Every kind in Method.needed_supplies must have at least
        one AVAILABLE Supply -> RunSupplyCoverageMismatchError
      - Every referencing Enclosure (every Enclosure containing any
        scoped Asset) must be Permitted-and-Active. When EVERY row
        fails the check -> RunRequiresPermittedEnclosureError;
        when some rows pass and some fail ->
        RunEnclosureCoverageMismatchError
      - Plan must not be Deprecated -> RunBoundPlanDeprecatedError
      - Subject (when set) must be Mounted or Measured
        -> RunSubjectNotMountableError
      - No bound Asset may be Decommissioned
        -> RunPlanAssetDecommissionedError
      - Union of current bound Asset families must cover Method's
        needed_family_ids -> RunCapabilitiesNotSatisfiedError
      - Effective parameters must validate against Method's
        parameters_schema (STRICT when schema is None; non-empty
        effective rejected)
        -> InvalidRunEffectiveParametersError
        (via validate_effective_parameters_against_method_schema)
      - All Plan wires must re-validate against current Asset.ports
        -> PlanWireAssetNotBoundError /
        PlanWirePortNotFoundError
        (via validate_wire_endpoints)
      - When campaign_id is set, Campaign must exist and be in
        Planned, Active, or Held -> RunCannotJoinCampaignError
      - Name must be valid -> InvalidRunNameError (via RunName VO)
      - pinned_calibration_ids cardinality must be within bound
        -> InvalidPinnedCalibrationsError
        (via validate_pinned_calibration_ids)

    `needed_family_ids_snapshot` is the Method's needed_family_ids
    set the handler resolved transitively from `plan.practice_id →
    practice.method_id → method.needed_family_ids`. Passed in as a
    plain frozenset so the decider stays purely state-driven.

    `effective_parameters` is the post-merge dict (Plan defaults +
    command overrides) the handler computed via `merge_patch`.
    `method_parameters_schema` is the Method's parameters_schema
    (None if Method declares no contract). The decider validates
    `effective_parameters` against the schema; STRICT when the schema
    is None — non-empty effective rejected (per audit reversal,
    mirrors the "no Capabilities + non-empty settings → reject"
    anchor). Emits RunStarted carrying BOTH the operator's overrides
    AND the resolved effective set.
    """
    if state is not None:
        raise RunAlreadyExistsError(state.id)

    # cross-BC clearance gate: at least one Safety
    # Clearance must be Active AND reference this Run's scope. The
    # handler pre-loaded every clearance whose bindings reference
    # the Run/Subject/Asset ids via deps.clearance_lookup. Partition
    # on status == "Active" to distinguish "no clearance at all"
    # (RunRequiresActiveClearanceError) from "clearance exists but
    # none Active" (RunClearanceCoverageMismatchError). Modern DDD
    # consensus (Khononov / Dudycz / Herberto Graca 2024-2025): cross-
    # context gating queries a replicated read model (here:
    # proj_safety_clearance_summary), not the upstream aggregate.
    if not context.referencing_clearances:
        raise RunRequiresActiveClearanceError(new_id)
    active_clearances = [c for c in context.referencing_clearances if c.status == "Active"]
    if not active_clearances:
        raise RunClearanceCoverageMismatchError(
            new_id,
            referencing_clearance_count=len(context.referencing_clearances),
        )

    # cross-BC Supply gate per
    # [[project_supply_preflight_gate_design]]: for every kind in
    # Method.needed_supplies, at least one Supply of that kind must
    # be registered (RunRequiresAvailableSupplyError when absent),
    # AND at least one of those registered Supplies must be in
    # status=Available (RunSupplyCoverageMismatchError when present
    # but none Available). Default-strict: Degraded does NOT pass;
    # operators with override authority use mark_supply_available
    # to declare a Supply Available before starting. Mirrors the
    # clearance-gate two-error pair pattern above.
    for kind in sorted(needed_supplies_snapshot):
        candidates = context.needed_supplies_satisfaction.get(kind, ())
        if not candidates:
            raise RunRequiresAvailableSupplyError(new_id, kind)
        if not any(s.status == "Available" for s in candidates):
            raise RunSupplyCoverageMismatchError(
                new_id,
                kind,
                frozenset((s.supply_id, s.status) for s in candidates),
            )

    # cross-BC Enclosure gate per [[project_enclosure_stage1_design]]:
    # every referencing Enclosure row must be `permit_status ==
    # "Permitted"` AND `lifecycle == "Active"`. Per L-pre-1 (always-
    # derive-from-Asset-chain), the scope set is derived in the
    # handler via `EnclosureLookup.find_for_assets`; this decider
    # treats an empty `context.referencing_enclosures` as Permit-by-
    # default (no Enclosure binds any scoped Asset). When any row
    # fails, the decider raises with `enclosure_status_summary`
    # carrying the `(enclosure_id, "permit_status|lifecycle")` tuple
    # for every failing Enclosure so the 409 names each blocker.
    # Default-strict: NotPermitted / Unknown / Decommissioned all fail
    # (the adapter excludes most Decommissioned rows at the read
    # layer; the decider treats any non-"Active" non-"Permitted" row
    # as a fail defensively).
    failing_rows = tuple(
        e
        for e in context.referencing_enclosures
        if not (e.permit_status == "Permitted" and e.lifecycle == "Active")
    )
    if failing_rows:
        # Build the user-facing summary as a frozenset (dedupes on
        # (id, label) for noise reduction in the 409 message). The
        # branch decision uses raw tuple lengths so a future adapter
        # that returns duplicate rows still classifies correctly.
        failing_summary = frozenset(
            (e.enclosure_id, f"{e.permit_status}|{e.lifecycle}") for e in failing_rows
        )
        if len(failing_rows) == len(context.referencing_enclosures):
            # Every referencing Enclosure failed the gate.
            raise RunRequiresPermittedEnclosureError(new_id, failing_summary)
        # Mixed: at least one passed, at least one failed.
        raise RunEnclosureCoverageMismatchError(new_id, failing_summary)

    if context.plan.status is PlanStatus.DEPRECATED:
        raise RunBoundPlanDeprecatedError(context.plan.id)

    if context.subject is not None and context.subject.status not in _SUBJECT_RUNNABLE_STATUSES:
        raise RunSubjectNotMountableError(
            context.subject.id, current_status=context.subject.status.value
        )

    decommissioned = sorted(
        (
            asset.id
            for asset in context.assets.values()
            if asset.lifecycle is AssetLifecycle.DECOMMISSIONED
        ),
        key=str,
    )
    if decommissioned:
        raise RunPlanAssetDecommissionedError(decommissioned)

    # Re-validation: union of CURRENT bound Asset capabilities must
    # cover Method's needs (per gate-review Q5; drift since Plan-bind
    # is real; Run-start is the last gate).
    union_capabilities: frozenset[UUID] = frozenset(
        cap for asset in context.assets.values() for cap in asset.family_ids
    )
    missing = needed_family_ids_snapshot - union_capabilities
    if missing:
        raise RunCapabilitiesNotSatisfiedError(missing)

    # 6g-c: validate the resolved (defaults + overrides) parameter set
    # against the owning Method's parameters_schema. Strict when the
    # schema is None: non-empty effective parameters are rejected
    # (per audit reversal; mirrors the "no Capabilities + non-
    # empty settings → reject" anchor; see
    # [[project_schema_validated_values_pattern]]).
    validate_effective_parameters_against_method_schema(
        effective_parameters, method_parameters_schema
    )

    # 6h: re-validate every Wire in the Plan's wires set against the
    # CURRENT Asset.ports state (drift since wire-add is real:
    # operators may have removed a referenced port between
    # add_plan_wire and start_run). Mirrors the capability re-validation
    # above. Wires whose endpoint Asset isn't in context.assets surface
    # as PlanWireAssetNotBoundError (the asset was removed from the
    # Plan's binding); wires whose port no longer exists surface as
    # PlanWirePortNotFoundError. See [[project_plan_wiring_design]]
    # §hot-swap procedure for the operational expectation.
    for wire in context.plan.wires:
        validate_wire_endpoints(
            wire,
            bound_asset_ids=context.plan.asset_ids,
            assets_by_id=context.assets,
        )

    # if the caller supplied campaign_id, the handler pre-
    # loaded the Campaign into the context. Verify the Campaign is in a
    # membership-eligible status (Planned / Active / Held); reject
    # terminal Campaigns (Closed / Abandoned) per the design memo
    # membership lock. The handler atomically writes the inverse
    # CampaignRunAdded event to the Campaign stream via
    # EventStore.append_streams.
    if command.campaign_id is not None:
        if context.campaign is None:
            # Defensive: the handler raises CampaignNotFoundError before
            # reaching the decider when the load returns None.
            raise RunCannotJoinCampaignError(
                run_id=new_id,
                campaign_id=command.campaign_id,
                campaign_status="<not found>",
            )
        if context.campaign.status not in _CAMPAIGN_MEMBERSHIP_ELIGIBLE_STATUSES:
            raise RunCannotJoinCampaignError(
                run_id=new_id,
                campaign_id=command.campaign_id,
                campaign_status=context.campaign.status.value,
            )

    name = RunName(command.name)  # validates + trims; raises InvalidRunNameError

    # cardinality cap on the AsShot pin set. NO cross-BC
    # existence check (revision-cited atomic-ID model; eventual-
    # consistency stance per [[project_calibration_design]] anti-hook
    # #3). Mirrors Data BC's register_dataset decider-time treatment
    # for Dataset.used_calibration_ids exactly.
    pinned_calibration_ids = validate_pinned_calibration_ids(command.pinned_calibration_ids)

    # build the acknowledged_cautions snapshot for the
    # RunStarted event payload. Per the Caution design memo, this
    # snapshot IS the ack (anti-pattern #7: ack lives on the
    # consumption event, never per-operator on the Caution
    # aggregate). NON-BLOCKING (anti-pattern #5): no precondition
    # check is added here; the decider only converts each
    # CautionReference from the context into a CautionAcknowledgement
    # VO and embeds the tuple verbatim.
    acknowledged_cautions = tuple(
        CautionAcknowledgement(
            caution_id=caution.caution_id,
            target_kind=caution.target_kind,
            target_id=caution.target_id,
            category=caution.category,
            severity=caution.severity,
            text_excerpt=caution.text_excerpt,
            workaround_excerpt=caution.workaround_excerpt,
        )
        for caution in context.active_cautions
    )

    run_events: list[RunStarted] = [
        RunStarted(
            run_id=new_id,
            name=name.value,
            plan_id=command.plan_id,
            subject_id=command.subject_id,
            raid=command.raid,
            override_parameters=command.override_parameters,
            effective_parameters=effective_parameters,
            trigger_source=command.trigger_source,
            external_refs=tuple(
                {"scheme": ref.scheme, "value": ref.value} for ref in command.external_refs
            ),
            acknowledged_cautions=acknowledged_cautions,
            campaign_id=command.campaign_id,
            decided_by_decision_id=command.decided_by_decision_id,
            # sort for deterministic byte-form on the event
            # payload (frozenset has no inherent order). The cardinality
            # check ran earlier via validate_pinned_calibration_ids (12b-5).
            pinned_calibration_ids=tuple(sorted(pinned_calibration_ids)),
            occurred_at=now,
        )
    ]

    # FCIS: when campaign_id is set, the decider also emits
    # the inverse `CampaignRunAdded` event for the Campaign stream. The
    # handler hands both lists to `EventStore.append_streams` as a
    # single atomic batch. When campaign_id is None, this list is empty
    # and the handler routes single-stream via `append`.
    campaign_events: list[CampaignRunAdded] = []
    if command.campaign_id is not None:
        campaign_events.append(
            CampaignRunAdded(
                campaign_id=command.campaign_id,
                run_id=new_id,
                occurred_at=now,
            )
        )

    return RunStartEvents(run_events=run_events, campaign_events=campaign_events)

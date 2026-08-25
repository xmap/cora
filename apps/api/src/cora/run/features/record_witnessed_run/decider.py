"""Pure decider for the `RecordWitnessedRun` command: the witnessed genesis.

Second genesis decider on the Run aggregate, after `start_run`. Where
`start_run` drives the act through CORA's own Conductor and hardcodes
`ConductMode.CONDUCTED`, this decider records that an external tool
already began a capture and hardcodes `ConductMode.WITNESSED`. Never the
other way around: `RecordWitnessedRun` carries no `conduct_mode` field for
either decider to read, so the mode is a property of which decider ran.

## The governing rule: refuse on what CORA can fix, witness what CORA cannot

CORA-side data faults (deprecated Plan, decommissioned Asset, capability
shortfall, bad wires, an absent Clearance or Supply) stay refusals here
exactly as at a driven start: they are loud, fixable, and the watcher
retries on the next capture. Only the two genuinely external live
facility signals, enclosure permit and beam availability, are witnessed
instead of enforced: `witness_safety_envelope` (shared with
`check_safety_envelope` via the same four gate functions in
`safety_envelope.py`, so the two paths cannot silently drift) still
raises for a failing clearance or supply gate, and returns a
`SafetyEnvelopeVerdict` for the other two.

## Validation order

Mirrors `start_run.decide`'s order for every CORA-side check it shares;
the trigger guard runs first (it is a request-shape rejection, not a
domain-state one) and the envelope witness runs where `start_run` runs
its enforcing envelope check.

Invariants:
  - State must be None (genesis-only) -> RunAlreadyExistsError
  - `trigger` must be the literal "Monitor" -> RunMonitorTriggerNotPermittedError
  - At least one Clearance must reference this Run's scope
    -> RunRequiresActiveClearanceError
  - At least one referencing Clearance must be Active
    -> RunClearanceCoverageMismatchError
  - Every kind in Method.needed_supplies must have at least
    one registered Supply -> RunRequiresAvailableSupplyError
  - Every kind in Method.needed_supplies must have at least
    one AVAILABLE Supply -> RunSupplyCoverageMismatchError
  - Plan must not be Deprecated -> RunBoundPlanDeprecatedError
  - Subject (when set) must be Mounted or Measured
    -> RunSubjectNotMountableError
  - No bound Asset may be Decommissioned
    -> RunPlanAssetDecommissionedError
  - Union of current bound Asset families must cover Method's
    needed_family_ids -> RunCapabilitiesNotSatisfiedError
  - Effective parameters (the Plan's own defaults, unmodified: this
    command carries no override_parameters) must validate against
    Method's parameters_schema -> InvalidRunEffectiveParametersError
    (via validate_effective_parameters_against_method_schema)
  - All Plan wires must re-validate against current Asset.ports
    -> PlanWireAssetNotBoundError / PlanWirePortNotFoundError
    (via validate_wire_endpoints)
  - Name must be valid -> InvalidRunNameError (via RunName VO)

Not enforced (witnessed instead, see above): the enclosure permit and
beam availability gates. Not present at all: campaign membership,
pinned_calibration_ids, input_dataset_ids, compute reachability -- the
command carries none of the fields those checks key on, so there is
nothing to validate.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from cora.equipment.aggregates.asset import AssetLifecycle
from cora.recipe.aggregates.plan import PlanStatus, validate_wire_endpoints
from cora.run.aggregates.run import (
    CautionAcknowledgement,
    ConductMode,
    Run,
    RunAlreadyExistsError,
    RunBoundPlanDeprecatedError,
    RunCapabilitiesNotSatisfiedError,
    RunMonitorTriggerNotPermittedError,
    RunName,
    RunPlanAssetDecommissionedError,
    RunStarted,
    RunSubjectNotMountableError,
    validate_effective_parameters_against_method_schema,
    witness_safety_envelope,
)
from cora.run.features.record_witnessed_run.command import RecordWitnessedRun
from cora.run.features.record_witnessed_run.context import RunWitnessedStartContext
from cora.shared.identifier import Identifier
from cora.subject.aggregates.subject import SubjectStatus

_SUBJECT_RUNNABLE_STATUSES: tuple[SubjectStatus, ...] = (
    SubjectStatus.MOUNTED,
    SubjectStatus.MEASURED,
)

_REQUIRED_TRIGGER = "Monitor"

_CAPTURE_CODE_SCHEME = "capture-code"


@dataclass(frozen=True)
class RunWitnessedStartEvents:
    """Events produced by a witnessed Run genesis: always exactly one."""

    run_events: list[RunStarted]


def decide(
    state: Run | None,
    command: RecordWitnessedRun,
    *,
    context: RunWitnessedStartContext,
    needed_family_ids_snapshot: frozenset[UUID],
    needed_supplies_snapshot: frozenset[str] = frozenset(),
    effective_parameters: dict[str, Any],
    method_parameters_schema: dict[str, Any] | None,
    now: datetime,
    new_id: UUID,
) -> RunWitnessedStartEvents:
    """Decide the events produced by recording a witnessed Run genesis."""
    if state is not None:
        raise RunAlreadyExistsError(state.id)

    if command.trigger != _REQUIRED_TRIGGER:
        raise RunMonitorTriggerNotPermittedError(new_id, command.trigger)

    # Witnessed, not enforced: enclosure permit and beam availability.
    # Clearance and Supply still raise here (CORA's own data, not a live
    # facility signal), via the exact same gate functions
    # check_safety_envelope composes, so the two entry points cannot
    # silently drift on what a gate checks.
    safety_envelope_verdict = witness_safety_envelope(
        run_id=new_id,
        referencing_clearances=context.referencing_clearances,
        needed_supplies_snapshot=needed_supplies_snapshot,
        needed_supplies_satisfaction=context.needed_supplies_satisfaction,
        referencing_enclosures=context.referencing_enclosures,
        beam_availability=context.beam_availability,
    )

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

    union_capabilities: frozenset[UUID] = frozenset(
        cap for asset in context.assets.values() for cap in asset.family_ids
    )
    missing = needed_family_ids_snapshot - union_capabilities
    if missing:
        raise RunCapabilitiesNotSatisfiedError(missing)

    validate_effective_parameters_against_method_schema(
        effective_parameters, method_parameters_schema
    )

    for wire in context.plan.wires:
        validate_wire_endpoints(
            wire,
            bound_asset_ids=context.plan.asset_ids,
            assets_by_id=context.assets,
        )

    name = RunName(command.name)  # validates + trims; raises InvalidRunNameError

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

    external_refs: tuple[dict[str, str], ...] = (
        {
            "scheme": Identifier(scheme=_CAPTURE_CODE_SCHEME, value=command.capture_code).scheme,
            "value": command.capture_code,
        },
    )
    if command.orchestrator_ref is not None:
        # A second, independent anti-corruption ref: an external
        # orchestrator's own run identifier for this capture (e.g. a
        # Bluesky RunEngine start-document uid), alongside `capture-code`,
        # never in place of it. Already a validated `Identifier` by the
        # time it reaches this command (see `RecordWitnessedRun`'s own
        # docstring), so no re-validation happens here beyond re-reading
        # its already-trimmed `scheme` / `value`.
        external_refs = (
            *external_refs,
            {
                "scheme": command.orchestrator_ref.scheme,
                "value": command.orchestrator_ref.value,
            },
        )

    run_events = [
        RunStarted(
            run_id=new_id,
            name=name.value,
            plan_id=command.plan_id,
            subject_id=command.subject_id,
            conduct_mode=ConductMode.WITNESSED,
            trigger_source=f"RunWitness:{command.capture_code}",
            effective_parameters=effective_parameters,
            external_refs=external_refs,
            acknowledged_cautions=acknowledged_cautions,
            safety_envelope_verdict=safety_envelope_verdict,
            capture_precondition_bypass_snapshot=command.capture_precondition_bypass_snapshot,
            occurred_at=now,
        )
    ]
    return RunWitnessedStartEvents(run_events=run_events)

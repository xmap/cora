"""Shared start-safety-envelope check (Run aggregate kernel).

The four cross-BC live-signal gates a Run must pass to begin,
clearance, supply, enclosure, and beam, are the same gates that must
still hold for a held Run to be safely resumed. Living in the aggregate
kernel (mirroring `plan.wires_validation.validate_wire_endpoints`) lets
the `start_run` decider, the RunSupervisor's pre-resume re-check, AND the
watched-genesis decider import one definition, so a change to any gate
applies to every consumer. Slice-to-slice sharing through a feature
module is banned (cross-slice independence), so this is the correct home.

Pure: no I/O. The caller (the `start_run` handler, the supervisor runtime
for resume, or the watched-genesis handler) loads the cross-aggregate
state and passes it in.

## Two entry points, four shared gates

`check_safety_envelope` raises the first failing gate, in the fixed order
clearance, supply, enclosure, beam; unchanged from before this module had
a second entry point. `witness_safety_envelope` is the watched-genesis
counterpart: per the roadmap's rule ("refuse on what CORA can fix, witness
what CORA cannot"), clearance and supply are CORA's own aggregates, so
they still RAISE on the watched path exactly as they do on the driven
path. Only enclosure and beam, the two genuinely external live facility
signals, become a recorded `SafetyEnvelopeVerdict` instead of a refusal.

Both entry points call the same four gate functions below, `check_*` for
the two that always raise and `*_gate_refusal` for the two that may
instead be witnessed. There is no third copy of any gate's logic: a
change to, say, the enclosure rule changes what both paths see by
construction, not by two authors remembering to keep two copies in sync.

The structural start-genesis validations (Plan-deprecated, Subject
status, Asset-decommissioned, capability re-validation, wire endpoints,
Campaign membership, name) deliberately stay in each decider: they are
genesis invariants, not live-signal gates, and a resume must NOT re-run
them (resume continues a Run that already passed them), and the watched
path's decider re-runs them exactly as the driven decider does (per the
roadmap: CORA-side data faults stay refusals on both paths).
"""

from collections.abc import Mapping
from uuid import UUID

from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.run.aggregates.run.state import (
    RunBeamAvailabilityUnknownError,
    RunClearanceCoverageMismatchError,
    RunEnclosureCoverageMismatchError,
    RunRequiresActiveClearanceError,
    RunRequiresAvailableSupplyError,
    RunRequiresOpenBeamShuttersError,
    RunRequiresPermittedEnclosureError,
    RunSupplyCoverageMismatchError,
    SafetyEnvelopeVerdict,
)


def clearance_gate_check(
    *,
    run_id: UUID,
    referencing_clearances: tuple[ClearanceLookupResult, ...],
) -> None:
    """Raise unless at least one Safety Clearance is Active AND references
    this Run's scope. The caller pre-loaded every clearance whose bindings
    reference the Run/Subject/Asset ids. Partition on status == "Active"
    to distinguish "no clearance at all" (RunRequiresActiveClearanceError)
    from "clearance exists but none Active" (RunClearanceCoverageMismatchError).
    Modern DDD consensus (Khononov / Dudycz / Herberto Graca 2024-2025):
    cross-context gating queries a replicated read model (here:
    proj_safety_clearance_summary), not the upstream aggregate.

    Always raises, never witnesses: a Clearance is a human authorization,
    not a live facility reading, per the roadmap's rule. This keeps the
    cross-port invariant fail-closed for EVERY Run, including a compute
    Run whose empty Asset scope makes the enclosure / beam gates below
    vacuous, and including a watched Run (see `test_compute_shaped_scope_
    still_requires_active_clearance`; any future split must not exempt
    either).
    """
    if not referencing_clearances:
        raise RunRequiresActiveClearanceError(run_id)
    active_clearances = [c for c in referencing_clearances if c.status == "Active"]
    if not active_clearances:
        raise RunClearanceCoverageMismatchError(
            run_id,
            referencing_clearance_count=len(referencing_clearances),
        )


def supply_gate_check(
    *,
    run_id: UUID,
    needed_supplies_snapshot: frozenset[str],
    needed_supplies_satisfaction: Mapping[str, tuple[SupplyLookupResult, ...]],
) -> None:
    """Raise unless, for every kind in Method.needed_supplies, at least one
    registered Supply of that kind is in status=Available, per
    [[project_supply_preflight_gate_design]]. Default-strict: Degraded
    does NOT pass; operators with override authority use
    mark_supply_available to declare a Supply Available before starting.
    Mirrors `clearance_gate_check`'s two-error pair pattern.

    Always raises, never witnesses, for the same reason as
    `clearance_gate_check`: Supply is CORA's own aggregate, not a live
    facility reading.
    """
    for kind in sorted(needed_supplies_snapshot):
        candidates = needed_supplies_satisfaction.get(kind, ())
        if not candidates:
            raise RunRequiresAvailableSupplyError(run_id, kind)
        if not any(s.status == "Available" for s in candidates):
            raise RunSupplyCoverageMismatchError(
                run_id,
                kind,
                frozenset((s.supply_id, s.status) for s in candidates),
            )


def enclosure_gate_refusal(
    *,
    run_id: UUID,
    referencing_enclosures: tuple[EnclosureLookupResult, ...],
) -> RunRequiresPermittedEnclosureError | RunEnclosureCoverageMismatchError | None:
    """Return the enclosure-gate refusal this Run would face, or None when
    the gate holds. Per [[project_enclosure_stage1_design]], every
    referencing Enclosure row must be `permit_status == "Permitted"` AND
    `lifecycle == "Active"`. Per L-pre-1 (always-derive-from-Asset-chain),
    the scope set is derived by the caller by collecting each scoped
    Asset's (and ancestor's) `located_in_enclosure_id` and loading them
    via `EnclosureLookup.find_by_ids`; an empty `referencing_enclosures`
    is Permit-by-default (no scoped Asset is located in any Enclosure).
    The returned error carries `enclosure_status_summary`, the
    `(enclosure_id, "permit_status|lifecycle")` tuple for every failing
    Enclosure, so a 409 built from it names each blocker. Default-strict:
    NotPermitted / Unknown / Decommissioned all fail (the adapter excludes
    most Decommissioned rows at the read layer; this treats any
    non-"Active" non-"Permitted" row as a fail defensively).

    Returns rather than raises: this is a live facility signal, so
    `check_safety_envelope` raises the return value while
    `witness_safety_envelope` records only whether it was None.
    """
    failing_rows = tuple(
        e
        for e in referencing_enclosures
        if not (e.permit_status == "Permitted" and e.lifecycle == "Active")
    )
    if not failing_rows:
        return None
    # Build the user-facing summary as a frozenset (dedupes on
    # (id, label) for noise reduction in the 409 message). The branch
    # decision uses raw tuple lengths so a future adapter that returns
    # duplicate rows still classifies correctly.
    failing_summary = frozenset(
        (e.enclosure_id, f"{e.permit_status}|{e.lifecycle}") for e in failing_rows
    )
    if len(failing_rows) == len(referencing_enclosures):
        # Every referencing Enclosure failed the gate.
        return RunRequiresPermittedEnclosureError(run_id, failing_summary)
    # Mixed: at least one passed, at least one failed.
    return RunEnclosureCoverageMismatchError(run_id, failing_summary)


def beam_gate_refusal(
    *,
    run_id: UUID,
    beam_availability: BeamAvailabilityLookupResult | None,
) -> RunBeamAvailabilityUnknownError | RunRequiresOpenBeamShuttersError | None:
    """Return the beam-gate refusal this Run would face, or None when the
    gate holds. Per BEAM-1: when the deployment configures beam PVs the
    caller reads the live front-end + station shutter states
    (BeamBlockingM, inverted polarity: 0 == open) and the ACIS FES-permit
    composite and passes the BeamAvailabilityLookupResult here. None means
    the deployment configures no beam PVs (beam-by-default). Fail-closed:
    a read whose quality is not Good (disconnected / bad PV) refuses
    rather than assume beam is open. Distinct axis from the Enclosure
    SecureM permit above: beam-open cycles per-scan, the enclosure permit
    is access-state.

    Returns rather than raises, same reason as `enclosure_gate_refusal`.
    """
    if beam_availability is None:
        return None
    if not beam_availability.quality_ok:
        return RunBeamAvailabilityUnknownError(run_id)
    blocking = frozenset(
        flag
        for flag, ok in (
            ("fes_open", beam_availability.fes_open),
            ("sbs_open", beam_availability.sbs_open),
            ("fes_permit", beam_availability.fes_permit),
        )
        if not ok
    )
    if blocking:
        return RunRequiresOpenBeamShuttersError(run_id, blocking)
    return None


def check_safety_envelope(
    *,
    run_id: UUID,
    referencing_clearances: tuple[ClearanceLookupResult, ...],
    needed_supplies_snapshot: frozenset[str],
    needed_supplies_satisfaction: Mapping[str, tuple[SupplyLookupResult, ...]],
    referencing_enclosures: tuple[EnclosureLookupResult, ...],
    beam_availability: BeamAvailabilityLookupResult | None,
) -> None:
    """Raise the first failing start-safety gate; return None if all pass.

    `run_id` is carried on each raised error (the new id at start_run,
    the existing run id at resume or at a watched genesis). Composed from
    the four gate functions above; behaviour, order, and every raised
    error's payload are unchanged from before this module gained a second
    entry point.
    """
    clearance_gate_check(run_id=run_id, referencing_clearances=referencing_clearances)
    supply_gate_check(
        run_id=run_id,
        needed_supplies_snapshot=needed_supplies_snapshot,
        needed_supplies_satisfaction=needed_supplies_satisfaction,
    )
    enclosure_refusal = enclosure_gate_refusal(
        run_id=run_id, referencing_enclosures=referencing_enclosures
    )
    if enclosure_refusal is not None:
        raise enclosure_refusal
    beam_refusal = beam_gate_refusal(run_id=run_id, beam_availability=beam_availability)
    if beam_refusal is not None:
        raise beam_refusal


def witness_safety_envelope(
    *,
    run_id: UUID,
    referencing_clearances: tuple[ClearanceLookupResult, ...],
    needed_supplies_snapshot: frozenset[str],
    needed_supplies_satisfaction: Mapping[str, tuple[SupplyLookupResult, ...]],
    referencing_enclosures: tuple[EnclosureLookupResult, ...],
    beam_availability: BeamAvailabilityLookupResult | None,
) -> SafetyEnvelopeVerdict:
    """Record a verdict on the two live facility signals instead of
    enforcing them; used only by the watched-genesis decider.

    Same six inputs and same clearance/supply behaviour as
    `check_safety_envelope`: both still raise on those two gates, because
    they are CORA-side data, not something the watcher can observe from
    the floor. Only enclosure and beam, evaluated by the exact same
    `enclosure_gate_refusal` / `beam_gate_refusal` functions
    `check_safety_envelope` uses, are converted to a bool instead of
    raised. This is what makes "both paths provably call the same
    predicates" a structural fact rather than a claim to trust.
    """
    clearance_gate_check(run_id=run_id, referencing_clearances=referencing_clearances)
    supply_gate_check(
        run_id=run_id,
        needed_supplies_snapshot=needed_supplies_snapshot,
        needed_supplies_satisfaction=needed_supplies_satisfaction,
    )
    return SafetyEnvelopeVerdict(
        enclosure_permitted=enclosure_gate_refusal(
            run_id=run_id, referencing_enclosures=referencing_enclosures
        )
        is None,
        beam_available=beam_gate_refusal(run_id=run_id, beam_availability=beam_availability)
        is None,
    )

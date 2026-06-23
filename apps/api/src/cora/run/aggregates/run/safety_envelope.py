"""Shared start-safety-envelope check (Run aggregate kernel).

The four cross-BC live-signal gates a Run must pass to begin,
clearance, supply, enclosure, and beam, are the same gates that must
still hold for a held Run to be safely resumed. Living in the aggregate
kernel (mirroring `plan.wires_validation.validate_wire_endpoints`) lets
both the `start_run` decider and the RunSupervisor's pre-resume re-check
import one definition, so a change to any gate applies to both the first
start and every later resume. Slice-to-slice sharing through a feature
module is banned (cross-slice independence), so this is the correct home.

Pure: no I/O. The caller (the `start_run` handler, or the supervisor
runtime for resume) loads the cross-aggregate state and passes it in.
Each gate raises the same Run-BC error it always did, in the same order;
the caller maps those to HTTP 409 / 4xx.

The structural start-genesis validations (Plan-deprecated, Subject
status, Asset-decommissioned, capability re-validation, wire endpoints,
Campaign membership, name) deliberately stay in the `start_run` decider:
they are genesis invariants, not live-signal gates, and a resume must
NOT re-run them (resume continues a Run that already passed them).
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
)


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
    the existing run id at resume).
    """
    # cross-BC clearance gate: at least one Safety Clearance must be
    # Active AND reference this Run's scope. The caller pre-loaded every
    # clearance whose bindings reference the Run/Subject/Asset ids.
    # Partition on status == "Active" to distinguish "no clearance at
    # all" (RunRequiresActiveClearanceError) from "clearance exists but
    # none Active" (RunClearanceCoverageMismatchError). Modern DDD
    # consensus (Khononov / Dudycz / Herberto Graca 2024-2025): cross-
    # context gating queries a replicated read model (here:
    # proj_safety_clearance_summary), not the upstream aggregate.
    #
    # Cross-port invariant: this clearance gate stays fail-closed for EVERY
    # Run, including a compute Run whose empty Asset scope makes the enclosure
    # / beam interlocks below vacuous. Any future per-port envelope split must
    # not exempt compute from clearance (see
    # test_compute_shaped_scope_still_requires_active_clearance).
    if not referencing_clearances:
        raise RunRequiresActiveClearanceError(run_id)
    active_clearances = [c for c in referencing_clearances if c.status == "Active"]
    if not active_clearances:
        raise RunClearanceCoverageMismatchError(
            run_id,
            referencing_clearance_count=len(referencing_clearances),
        )

    # cross-BC Supply gate per [[project_supply_preflight_gate_design]]:
    # for every kind in Method.needed_supplies, at least one Supply of
    # that kind must be registered (RunRequiresAvailableSupplyError when
    # absent), AND at least one of those registered Supplies must be in
    # status=Available (RunSupplyCoverageMismatchError when present but
    # none Available). Default-strict: Degraded does NOT pass; operators
    # with override authority use mark_supply_available to declare a
    # Supply Available before starting. Mirrors the clearance-gate two-
    # error pair pattern above.
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

    # cross-BC Enclosure gate per [[project_enclosure_stage1_design]]:
    # every referencing Enclosure row must be `permit_status ==
    # "Permitted"` AND `lifecycle == "Active"`. Per L-pre-1 (always-
    # derive-from-Asset-chain), the scope set is derived by the caller by
    # collecting each scoped Asset's (and ancestor's)
    # `located_in_enclosure_id` and loading them via
    # `EnclosureLookup.find_by_ids`; an empty `referencing_enclosures` is
    # Permit-by-default (no scoped Asset is located in any Enclosure).
    # When any row fails, raise with `enclosure_status_summary` carrying
    # the `(enclosure_id, "permit_status|lifecycle")` tuple for every
    # failing Enclosure so the 409 names each blocker. Default-strict:
    # NotPermitted / Unknown / Decommissioned all fail (the adapter
    # excludes most Decommissioned rows at the read layer; this treats
    # any non-"Active" non-"Permitted" row as a fail defensively).
    failing_rows = tuple(
        e
        for e in referencing_enclosures
        if not (e.permit_status == "Permitted" and e.lifecycle == "Active")
    )
    if failing_rows:
        # Build the user-facing summary as a frozenset (dedupes on
        # (id, label) for noise reduction in the 409 message). The branch
        # decision uses raw tuple lengths so a future adapter that
        # returns duplicate rows still classifies correctly.
        failing_summary = frozenset(
            (e.enclosure_id, f"{e.permit_status}|{e.lifecycle}") for e in failing_rows
        )
        if len(failing_rows) == len(referencing_enclosures):
            # Every referencing Enclosure failed the gate.
            raise RunRequiresPermittedEnclosureError(run_id, failing_summary)
        # Mixed: at least one passed, at least one failed.
        raise RunEnclosureCoverageMismatchError(run_id, failing_summary)

    # cross-BC beam-availability gate per BEAM-1: when the deployment
    # configures beam PVs the caller reads the live front-end + station
    # shutter states (BeamBlockingM, inverted polarity: 0 == open) and
    # the ACIS FES-permit composite and passes the
    # BeamAvailabilityLookupResult here. None means the deployment
    # configures no beam PVs (beam-by-default). Fail-closed: a read whose
    # quality is not Good (disconnected / bad PV) refuses rather than
    # assume beam is open. Distinct axis from the Enclosure SecureM
    # permit above: beam-open cycles per-scan, the enclosure permit is
    # access-state.
    if beam_availability is not None:
        if not beam_availability.quality_ok:
            raise RunBeamAvailabilityUnknownError(run_id)
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
            raise RunRequiresOpenBeamShuttersError(run_id, blocking)

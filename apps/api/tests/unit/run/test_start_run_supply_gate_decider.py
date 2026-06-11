"""Decider tests for the cross-BC Supply pre-flight gate on start_run.

Pins the two error paths:
  - kind in `needed_supplies_snapshot` absent from `needed_supplies_satisfaction`
    -> `RunRequiresAvailableSupplyError`
  - kind exists in satisfaction but every entry has status != "Available"
    -> `RunSupplyCoverageMismatchError`

Plus the happy path: at least one AVAILABLE SupplyReference satisfies
the kind (Degraded and other non-AVAILABLE entries don't count per the
shared AVAILABLE-only lock from project_supply_preflight_gate_design).

Empty `needed_supplies_snapshot` short-circuits the gate (Methods with
no needed_supplies pass trivially).
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.equipment.aggregates.asset import (
    Asset,
    AssetLifecycle,
    AssetName,
    AssetTier,
)
from cora.infrastructure.ports.clearance_lookup import ClearanceReference
from cora.infrastructure.ports.supply_lookup import SupplyReference
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import (
    RunRequiresAvailableSupplyError,
    RunSupplyCoverageMismatchError,
)
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


def _ref(kind: str, status: str) -> SupplyReference:
    return SupplyReference(
        supply_id=uuid4(),
        kind=kind,
        name=f"<test {kind}>",
        status=status,
        facility_code="<test-facility>",
    )


def _active_clearance() -> ClearanceReference:
    return ClearanceReference(
        clearance_id=uuid4(),
        status="Active",
        template_id=uuid4(),
        template_code="RadiationWork",
        facility_code="aps",
    )


def _context(
    needed_supplies_satisfaction: dict[str, tuple[SupplyReference, ...]],
) -> tuple[RunStartContext, frozenset[UUID]]:
    """Build a RunStartContext that passes every check EXCEPT the
    Supply gate. Returns the context + the needed_family_ids the handler
    would resolve so the decider sees a satisfied Plan on the non-
    Supply dimensions."""
    cap = uuid4()
    asset_id = uuid4()
    plan = Plan(
        id=uuid4(),
        name=PlanName("Pilot"),
        practice_id=uuid4(),
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
    )
    asset = Asset(
        id=asset_id,
        name=AssetName("EigerDetector"),
        tier=AssetTier.DEVICE,
        parent_id=uuid4(),
        lifecycle=AssetLifecycle.ACTIVE,
        family_ids=frozenset({cap}),
    )
    subject = Subject(
        id=uuid4(),
        name=SubjectName("PorousCeramicSample"),
        status=SubjectStatus.MOUNTED,
    )
    context = RunStartContext(
        plan=plan,
        subject=subject,
        assets={asset_id: asset},
        referencing_clearances=(_active_clearance(),),
        needed_supplies_satisfaction=needed_supplies_satisfaction,
    )
    return context, frozenset({cap})


def _start(
    needs: frozenset[str],
    context: RunStartContext,
    new_id: UUID,
    needed_family_ids: frozenset[UUID],
):
    return start_run.decide(
        state=None,
        command=StartRun(
            name="Run",
            plan_id=context.plan.id,
            subject_id=context.subject.id if context.subject else None,
        ),
        context=context,
        needed_family_ids_snapshot=needed_family_ids,
        needed_supplies_snapshot=needs,
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )


@pytest.mark.unit
def test_decide_passes_when_no_supplies_needed() -> None:
    """Empty needed_supplies_snapshot short-circuits the gate."""
    context, needs = _context(needed_supplies_satisfaction={})
    decision = _start(frozenset(), context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_passes_when_every_needed_kind_has_an_available_supply() -> None:
    """One AVAILABLE per kind satisfies the gate; non-AVAILABLE peers don't matter."""
    context, needs = _context(
        needed_supplies_satisfaction={
            "LiquidNitrogen": (
                _ref("LiquidNitrogen", "Degraded"),
                _ref("LiquidNitrogen", "Available"),
            ),
            "PhotonBeam": (_ref("PhotonBeam", "Available"),),
        }
    )
    decision = _start(frozenset({"LiquidNitrogen", "PhotonBeam"}), context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_raises_requires_available_when_kind_absent_from_satisfaction() -> None:
    """Needed kind missing from satisfaction -> RunRequiresAvailableSupplyError."""
    context, needs = _context(
        needed_supplies_satisfaction={
            "LiquidNitrogen": (_ref("LiquidNitrogen", "Available"),),
        }
    )
    new_id = uuid4()
    with pytest.raises(RunRequiresAvailableSupplyError) as exc_info:
        _start(frozenset({"LiquidNitrogen", "PhotonBeam"}), context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.kind == "PhotonBeam"


@pytest.mark.unit
@pytest.mark.parametrize("status", ["Unknown", "Degraded", "Unavailable", "Recovering"])
def test_decide_raises_coverage_mismatch_when_no_supply_is_available(status: str) -> None:
    """Kind exists in satisfaction but none AVAILABLE -> RunSupplyCoverageMismatchError.

    Parametrized over every non-AVAILABLE non-Decommissioned status to
    pin the AVAILABLE-only semantics shared with the monitor-trigger
    memo. Decommissioned is excluded at the read layer per
    [[project_deregister_supply_design]] partial UNIQUE INDEX, so it
    never reaches the decider."""
    only_supply = _ref("LiquidNitrogen", status)
    context, needs = _context(
        needed_supplies_satisfaction={"LiquidNitrogen": (only_supply,)},
    )
    new_id = uuid4()
    with pytest.raises(RunSupplyCoverageMismatchError) as exc_info:
        _start(frozenset({"LiquidNitrogen"}), context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.kind == "LiquidNitrogen"
    assert (only_supply.supply_id, status) in exc_info.value.supply_status_summary


@pytest.mark.unit
def test_decide_supply_gate_diagnoses_first_failing_kind_deterministically() -> None:
    """Multiple unsatisfied kinds: the decider raises for the first one
    in sorted iteration order. Pins the deterministic ordering so the
    operator-facing error message is reproducible across requests."""
    context, needs = _context(needed_supplies_satisfaction={})
    with pytest.raises(RunRequiresAvailableSupplyError) as exc_info:
        _start(frozenset({"PhotonBeam", "LiquidNitrogen"}), context, uuid4(), needs)
    # Sorted alphabetically: LiquidNitrogen comes before PhotonBeam.
    assert exc_info.value.kind == "LiquidNitrogen"

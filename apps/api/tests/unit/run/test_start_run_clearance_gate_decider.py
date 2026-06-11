"""Decider tests for the cross-BC clearance gate on start_run.

Pins the two error paths:
  - empty `referencing_clearances` tuple -> `RunRequiresActiveClearanceError`
  - non-empty `referencing_clearances` but none Active ->
    `RunClearanceCoverageMismatchError`

Plus the happy path: a non-Active clearance alongside ONE Active
clearance passes the gate (only one Active is required).

The gate fires BEFORE the existing Plan/Subject/Asset checks so an
invalid clearance setup surfaces before unrelated invariants.
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
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import (
    RunClearanceCoverageMismatchError,
    RunRequiresActiveClearanceError,
)
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)


def _context(
    referencing_clearances: tuple[ClearanceReference, ...],
) -> tuple[RunStartContext, frozenset[UUID]]:
    """Build a RunStartContext that would pass every check EXCEPT the
    clearance gate. Returns the context + the needed_family_ids the
    handler would resolve so the decider sees a fully-satisfied Plan
    on the non-clearance dimensions."""
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
        referencing_clearances=referencing_clearances,
    )
    return context, frozenset({cap})


def _ref(status: str) -> ClearanceReference:
    return ClearanceReference(
        clearance_id=uuid4(),
        status=status,
        template_id=uuid4(),
        template_code="ESAF",
        facility_code="aps",
    )


@pytest.mark.unit
def test_decide_raises_requires_active_when_no_clearance_references_the_run() -> None:
    """Empty tuple = no clearance references this Run's scope -> Requires error."""
    context, needs = _context(referencing_clearances=())
    new_id = uuid4()
    with pytest.raises(RunRequiresActiveClearanceError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(
                name="Run",
                plan_id=context.plan.id,
                subject_id=context.subject.id if context.subject else None,
            ),
            context=context,
            needed_family_ids_snapshot=needs,
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=new_id,
        )
    assert exc_info.value.run_id == new_id


@pytest.mark.unit
@pytest.mark.parametrize(
    "status",
    ["Defined", "Submitted", "UnderReview", "Approved", "Expired", "Rejected", "Superseded"],
)
def test_decide_raises_coverage_mismatch_when_no_clearance_is_active(status: str) -> None:
    """Clearances reference the Run but none Active -> CoverageMismatch error."""
    context, needs = _context(referencing_clearances=(_ref(status),))
    new_id = uuid4()
    with pytest.raises(RunClearanceCoverageMismatchError) as exc_info:
        start_run.decide(
            state=None,
            command=StartRun(
                name="Run",
                plan_id=context.plan.id,
                subject_id=context.subject.id if context.subject else None,
            ),
            context=context,
            needed_family_ids_snapshot=needs,
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=new_id,
        )
    assert exc_info.value.run_id == new_id
    assert exc_info.value.referencing_clearance_count == 1


@pytest.mark.unit
def test_decide_passes_when_at_least_one_active_clearance_covers() -> None:
    """One Active alongside non-Active clearances is enough to pass the gate."""
    context, needs = _context(
        referencing_clearances=(
            _ref("Defined"),
            _ref("Active"),
            _ref("Superseded"),
        )
    )
    decision = start_run.decide(
        state=None,
        command=StartRun(
            name="Run",
            plan_id=context.plan.id,
            subject_id=context.subject.id if context.subject else None,
        ),
        context=context,
        needed_family_ids_snapshot=needs,
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=uuid4(),
    )
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_clearance_gate_fires_before_plan_status_check() -> None:
    """Clearance gate runs FIRST: a missing clearance surfaces before
    a deprecated Plan would. The decider's check order is documented
    in its module docstring; this test pins it."""
    context, needs = _context(referencing_clearances=())
    # Force Plan to Deprecated -- without the clearance gate first
    # this would raise RunBoundPlanDeprecatedError instead.
    deprecated_plan = Plan(
        id=context.plan.id,
        name=context.plan.name,
        practice_id=context.plan.practice_id,
        asset_ids=context.plan.asset_ids,
        status=PlanStatus.DEPRECATED,
    )
    deprecated_context = RunStartContext(
        plan=deprecated_plan,
        subject=context.subject,
        assets=context.assets,
        referencing_clearances=(),
    )
    with pytest.raises(RunRequiresActiveClearanceError):
        start_run.decide(
            state=None,
            command=StartRun(
                name="Run",
                plan_id=deprecated_plan.id,
                subject_id=context.subject.id if context.subject else None,
            ),
            context=deprecated_context,
            needed_family_ids_snapshot=needs,
            effective_parameters={},
            method_parameters_schema=None,
            now=_NOW,
            new_id=uuid4(),
        )

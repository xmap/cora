"""Decider tests for the cross-BC Enclosure pre-flight gate on start_run.

Pins the two error paths:
  - every referencing Enclosure row fails the Permitted-and-Active
    check -> `RunRequiresPermittedEnclosureError`
  - some referencing rows pass, some fail ->
    `RunEnclosureCoverageMismatchError`

Plus the happy paths:
  - empty `referencing_enclosures` tuple is Permit-by-default (per
    [[project_enclosure_stage1_design]] L-pre-1: Asset-chain that
    traces to no Enclosure has no enclosure-permit gate).
  - one Active+Permitted row alongside any number of additional
    Active+Permitted rows passes.

Default-strict per the design memo: NotPermitted, Unknown, and any
non-Active lifecycle value all fail the gate.
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
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import (
    RunEnclosureCoverageMismatchError,
    RunRequiresPermittedEnclosureError,
)
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


def _enclosure_ref(
    *,
    permit_status: str = "Permitted",
    lifecycle: str = "Active",
) -> EnclosureLookupResult:
    return EnclosureLookupResult(
        enclosure_id=uuid4(),
        name="<test enclosure>",
        permit_status=permit_status,
        lifecycle=lifecycle,
        observed_at=None,
        source_kind=None,
        source_id=None,
    )


def _active_clearance() -> ClearanceLookupResult:
    return ClearanceLookupResult(
        clearance_id=uuid4(),
        status="Active",
        template_id=uuid4(),
        template_code="RadiationWork",
        facility_code="aps",
    )


def _context(
    referencing_enclosures: tuple[EnclosureLookupResult, ...],
) -> tuple[RunStartContext, frozenset[UUID]]:
    """Build a RunStartContext that would pass every check EXCEPT the
    Enclosure gate. Returns the context + the needed_family_ids the
    handler would resolve so the decider sees a satisfied Plan on the
    non-Enclosure dimensions."""
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
        referencing_enclosures=referencing_enclosures,
    )
    return context, frozenset({cap})


def _start(
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
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )


@pytest.mark.unit
def test_decide_passes_when_no_enclosure_binds_any_asset() -> None:
    """Empty referencing_enclosures is Permit-by-default per L-pre-1."""
    context, needs = _context(referencing_enclosures=())
    decision = _start(context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_passes_when_every_referencing_enclosure_is_permitted_and_active() -> None:
    """All Permitted+Active rows pass the gate."""
    context, needs = _context(
        referencing_enclosures=(
            _enclosure_ref(permit_status="Permitted", lifecycle="Active"),
            _enclosure_ref(permit_status="Permitted", lifecycle="Active"),
        )
    )
    decision = _start(context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
@pytest.mark.parametrize("permit_status", ["NotPermitted", "Unknown"])
def test_decide_raises_requires_permitted_when_every_row_fails(permit_status: str) -> None:
    """Every referencing Enclosure fails -> RunRequiresPermittedEnclosureError.

    Parametrized over NotPermitted and Unknown to pin the default-strict
    posture: only Permitted+Active passes; everything else fails.
    """
    only = _enclosure_ref(permit_status=permit_status)
    context, needs = _context(referencing_enclosures=(only,))
    new_id = uuid4()
    with pytest.raises(RunRequiresPermittedEnclosureError) as exc_info:
        _start(context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert (only.enclosure_id, f"{permit_status}|Active") in exc_info.value.enclosure_status_summary


@pytest.mark.unit
def test_decide_raises_requires_permitted_when_lifecycle_decommissioned() -> None:
    """Defensive: a Decommissioned row reaching the decider still fails.

    The Postgres adapter excludes Decommissioned rows at the read
    layer via the `lifecycle = 'Active'` partial-index posture, but
    the decider treats any non-Active lifecycle as a fail defensively
    so consumers can't accidentally bypass the gate by injecting one.
    """
    only = _enclosure_ref(permit_status="Permitted", lifecycle="Decommissioned")
    context, needs = _context(referencing_enclosures=(only,))
    new_id = uuid4()
    with pytest.raises(RunRequiresPermittedEnclosureError) as exc_info:
        _start(context, new_id, needs)
    assert exc_info.value.run_id == new_id
    summary = exc_info.value.enclosure_status_summary
    assert (only.enclosure_id, "Permitted|Decommissioned") in summary


@pytest.mark.unit
def test_decide_raises_coverage_mismatch_when_some_rows_pass_and_some_fail() -> None:
    """Mixed-status set -> RunEnclosureCoverageMismatchError.

    The CoverageMismatch branch fires when at least one referencing
    row passes AND at least one fails. Mirrors the Supply gate's
    Coverage-vs-Requires split.
    """
    passing = _enclosure_ref(permit_status="Permitted", lifecycle="Active")
    failing = _enclosure_ref(permit_status="NotPermitted", lifecycle="Active")
    context, needs = _context(referencing_enclosures=(passing, failing))
    new_id = uuid4()
    with pytest.raises(RunEnclosureCoverageMismatchError) as exc_info:
        _start(context, new_id, needs)
    assert exc_info.value.run_id == new_id
    summary = exc_info.value.enclosure_status_summary
    # Only the failing row appears in the summary; the passing row is
    # not flagged.
    assert (failing.enclosure_id, "NotPermitted|Active") in summary
    assert all(eid != passing.enclosure_id for eid, _ in summary)


@pytest.mark.unit
def test_decide_raises_requires_when_all_bindings_fail_including_duplicates() -> None:
    """Duplicate failing rows still classify as Requires, not CoverageMismatch.

    The decider compares `len(failing_rows) == len(context.referencing_enclosures)`
    on the raw tuples so duplicate adapter rows do not flip the
    classification from Requires to CoverageMismatch. The frozenset
    summary still dedups by (enclosure_id, label), which is why the
    branch deliberately reads raw lengths instead of summary cardinality.
    """
    failing = _enclosure_ref(permit_status="NotPermitted", lifecycle="Active")
    context, needs = _context(referencing_enclosures=(failing, failing))
    new_id = uuid4()
    with pytest.raises(RunRequiresPermittedEnclosureError) as exc_info:
        _start(context, new_id, needs)
    assert exc_info.value.run_id == new_id
    summary = exc_info.value.enclosure_status_summary
    assert (failing.enclosure_id, "NotPermitted|Active") in summary
    assert len(summary) == 1


@pytest.mark.unit
def test_decide_raises_coverage_mismatch_when_passing_rows_are_duplicated() -> None:
    """Duplicate passing rows still classify as CoverageMismatch when any row fails.

    Seeding (passing, passing, failing) means `len(failing_rows) == 1`
    but `len(context.referencing_enclosures) == 3`, so the branch fires
    CoverageMismatch even though the frozenset summary collapses the
    duplicate passing row. Guards against a regression that swaps the
    raw-tuple check for a summary-cardinality check.
    """
    passing = _enclosure_ref(permit_status="Permitted", lifecycle="Active")
    failing = _enclosure_ref(permit_status="NotPermitted", lifecycle="Active")
    context, needs = _context(referencing_enclosures=(passing, passing, failing))
    new_id = uuid4()
    with pytest.raises(RunEnclosureCoverageMismatchError) as exc_info:
        _start(context, new_id, needs)
    assert exc_info.value.run_id == new_id
    summary = exc_info.value.enclosure_status_summary
    assert (failing.enclosure_id, "NotPermitted|Active") in summary
    assert all(eid != passing.enclosure_id for eid, _ in summary)

"""Decider tests for the cross-BC Enclosure pre-flight gate on start_procedure.

Pins the two error paths:
  - every referencing Enclosure row fails the Permitted-and-Active
    check -> `ProcedureRequiresPermittedEnclosureError`
  - some rows pass, some fail ->
    `ProcedureEnclosureCoverageMismatchError`

Plus the happy paths:
  - empty `referencing_enclosures` is Permit-by-default (facility-
    envelope Procedures with empty target_asset_ids, OR Procedures
    whose Assets are not contained by any Enclosure).
  - one Active+Permitted row alongside additional Active+Permitted
    rows passes.

Default-strict per [[project_enclosure_stage1_design]]: NotPermitted,
Unknown, and any non-Active lifecycle all fail. Mirrors start_run's
enclosure gate test shape exactly.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.enclosure_lookup import EnclosureReference
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureEnclosureCoverageMismatchError,
    ProcedureName,
    ProcedureRequiresPermittedEnclosureError,
    ProcedureStatus,
)
from cora.operation.features import start_procedure
from cora.operation.features.start_procedure import ProcedureStartContext, StartProcedure

_NOW = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


def _enclosure_ref(
    *,
    permit_status: str = "Permitted",
    lifecycle: str = "Active",
) -> EnclosureReference:
    return EnclosureReference(
        enclosure_id=uuid4(),
        name="<test enclosure>",
        containing_asset_id=uuid4(),
        permit_status=permit_status,
        lifecycle=lifecycle,
        observed_at=None,
        source_kind=None,
        source_id=None,
    )


def _procedure(procedure_id: UUID | None = None) -> Procedure:
    return Procedure(
        id=procedure_id or uuid4(),
        name=ProcedureName("Bakeout"),
        kind="bakeout",
        target_asset_ids=frozenset(),
        status=ProcedureStatus.DEFINED,
    )


def _context(
    referencing_enclosures: tuple[EnclosureReference, ...],
) -> ProcedureStartContext:
    return ProcedureStartContext(
        assets={},
        referencing_enclosures=referencing_enclosures,
    )


def _start(procedure: Procedure, context: ProcedureStartContext):
    return start_procedure.decide(
        state=procedure,
        command=StartProcedure(procedure_id=procedure.id),
        context=context,
        now=_NOW,
    )


@pytest.mark.unit
def test_decide_passes_when_no_enclosure_binds_any_asset() -> None:
    """Empty referencing_enclosures is Permit-by-default per L-pre-1."""
    procedure = _procedure()
    decision = _start(procedure, _context(referencing_enclosures=()))
    assert len(decision) == 1


@pytest.mark.unit
def test_decide_passes_when_every_referencing_enclosure_is_permitted_and_active() -> None:
    procedure = _procedure()
    decision = _start(
        procedure,
        _context(
            referencing_enclosures=(
                _enclosure_ref(permit_status="Permitted", lifecycle="Active"),
                _enclosure_ref(permit_status="Permitted", lifecycle="Active"),
            )
        ),
    )
    assert len(decision) == 1


@pytest.mark.unit
@pytest.mark.parametrize("permit_status", ["NotPermitted", "Unknown"])
def test_decide_raises_requires_permitted_when_every_row_fails(permit_status: str) -> None:
    """Every referencing row fails -> ProcedureRequiresPermittedEnclosureError."""
    only = _enclosure_ref(permit_status=permit_status)
    procedure = _procedure()
    with pytest.raises(ProcedureRequiresPermittedEnclosureError) as exc_info:
        _start(procedure, _context(referencing_enclosures=(only,)))
    assert exc_info.value.procedure_id == procedure.id
    assert (only.enclosure_id, f"{permit_status}|Active") in exc_info.value.enclosure_status_summary


@pytest.mark.unit
def test_decide_raises_requires_permitted_when_lifecycle_decommissioned() -> None:
    """Defensive: a Decommissioned row reaching the decider still fails."""
    only = _enclosure_ref(permit_status="Permitted", lifecycle="Decommissioned")
    procedure = _procedure()
    with pytest.raises(ProcedureRequiresPermittedEnclosureError) as exc_info:
        _start(procedure, _context(referencing_enclosures=(only,)))
    assert exc_info.value.procedure_id == procedure.id
    summary = exc_info.value.enclosure_status_summary
    assert (only.enclosure_id, "Permitted|Decommissioned") in summary


@pytest.mark.unit
def test_decide_raises_coverage_mismatch_when_some_rows_pass_and_some_fail() -> None:
    """Mixed-status set -> ProcedureEnclosureCoverageMismatchError."""
    passing = _enclosure_ref(permit_status="Permitted", lifecycle="Active")
    failing = _enclosure_ref(permit_status="NotPermitted", lifecycle="Active")
    procedure = _procedure()
    with pytest.raises(ProcedureEnclosureCoverageMismatchError) as exc_info:
        _start(procedure, _context(referencing_enclosures=(passing, failing)))
    assert exc_info.value.procedure_id == procedure.id
    summary = exc_info.value.enclosure_status_summary
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
    procedure = _procedure()
    with pytest.raises(ProcedureRequiresPermittedEnclosureError) as exc_info:
        _start(procedure, _context(referencing_enclosures=(failing, failing)))
    assert exc_info.value.procedure_id == procedure.id
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
    procedure = _procedure()
    with pytest.raises(ProcedureEnclosureCoverageMismatchError) as exc_info:
        _start(procedure, _context(referencing_enclosures=(passing, passing, failing)))
    assert exc_info.value.procedure_id == procedure.id
    summary = exc_info.value.enclosure_status_summary
    assert (failing.enclosure_id, "NotPermitted|Active") in summary
    assert all(eid != passing.enclosure_id for eid, _ in summary)

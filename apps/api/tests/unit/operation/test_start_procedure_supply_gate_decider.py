"""Decider tests for the cross-BC Supply pre-flight gate on start_procedure.

Pins the two error paths:
  - kind in `needed_supplies_snapshot` absent from `needed_supplies_satisfaction`
    -> `ProcedureRequiresAvailableSupplyError`
  - kind exists in satisfaction but every entry has status != "Available"
    -> `ProcedureSupplyCoverageMismatchError`

Plus the happy path: at least one AVAILABLE SupplyLookupResult satisfies
the kind. Standalone Procedures (no parent_run_id) pass trivially
because the handler passes an empty `needed_supplies_snapshot`.
Phase-of-Run Procedures inherit their parent Run's
Method.needed_supplies via the handler's parent_run_id resolution
chain per [[project_supply_preflight_gate_design]].
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureName,
    ProcedureRequiresAvailableSupplyError,
    ProcedureStatus,
    ProcedureSupplyCoverageMismatchError,
)
from cora.operation.features import start_procedure
from cora.operation.features.start_procedure import ProcedureStartContext, StartProcedure

_NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


def _ref(kind: str, status: str) -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=uuid4(),
        kind=kind,
        name=f"<test {kind}>",
        status=status,
        facility_code="<test-facility>",
    )


def _procedure(procedure_id: UUID | None = None) -> Procedure:
    return Procedure(
        id=procedure_id or uuid4(),
        name=ProcedureName("LN2 bakeout"),
        kind="bakeout",
        target_asset_ids=frozenset(),
        status=ProcedureStatus.DEFINED,
    )


def _context(
    needed_supplies_satisfaction: dict[str, tuple[SupplyLookupResult, ...]],
) -> ProcedureStartContext:
    return ProcedureStartContext(
        assets={},
        needed_supplies_satisfaction=needed_supplies_satisfaction,
    )


def _start(
    needs: frozenset[str],
    procedure: Procedure,
    context: ProcedureStartContext,
):
    return start_procedure.decide(
        state=procedure,
        command=StartProcedure(procedure_id=procedure.id),
        context=context,
        needed_supplies_snapshot=needs,
        now=_NOW,
    )


@pytest.mark.unit
def test_decide_passes_when_no_supplies_needed_standalone_procedure() -> None:
    """Standalone Procedure (handler passes empty snapshot) skips the gate."""
    proc = _procedure()
    decision = _start(frozenset(), proc, _context({}))
    assert len(decision) == 1


@pytest.mark.unit
def test_decide_passes_when_every_needed_kind_has_an_available_supply() -> None:
    """Phase-of-Run Procedure with satisfied parent Method.needed_supplies passes."""
    proc = _procedure()
    context = _context(
        {
            "LiquidNitrogen": (
                _ref("LiquidNitrogen", "Unavailable"),
                _ref("LiquidNitrogen", "Available"),
            ),
            "PhotonBeam": (_ref("PhotonBeam", "Available"),),
        }
    )
    decision = _start(frozenset({"LiquidNitrogen", "PhotonBeam"}), proc, context)
    assert len(decision) == 1


@pytest.mark.unit
def test_decide_raises_requires_available_when_kind_absent_from_satisfaction() -> None:
    """Needed kind missing from satisfaction -> ProcedureRequiresAvailableSupplyError."""
    proc = _procedure()
    context = _context({"LiquidNitrogen": (_ref("LiquidNitrogen", "Available"),)})
    with pytest.raises(ProcedureRequiresAvailableSupplyError) as exc_info:
        _start(frozenset({"LiquidNitrogen", "PhotonBeam"}), proc, context)
    assert exc_info.value.procedure_id == proc.id
    assert exc_info.value.kind == "PhotonBeam"


@pytest.mark.unit
@pytest.mark.parametrize("status", ["Unknown", "Degraded", "Unavailable", "Recovering"])
def test_decide_raises_coverage_mismatch_when_no_supply_is_available(status: str) -> None:
    """Kind exists in satisfaction but none AVAILABLE -> ProcedureSupplyCoverageMismatchError."""
    proc = _procedure()
    only_supply = _ref("LiquidNitrogen", status)
    context = _context({"LiquidNitrogen": (only_supply,)})
    with pytest.raises(ProcedureSupplyCoverageMismatchError) as exc_info:
        _start(frozenset({"LiquidNitrogen"}), proc, context)
    assert exc_info.value.procedure_id == proc.id
    assert exc_info.value.kind == "LiquidNitrogen"
    assert (only_supply.supply_id, status) in exc_info.value.supply_status_summary


@pytest.mark.unit
def test_decide_supply_gate_diagnoses_first_failing_kind_deterministically() -> None:
    """Multiple unsatisfied kinds: raise for the first in sorted order."""
    proc = _procedure()
    context = _context({})
    with pytest.raises(ProcedureRequiresAvailableSupplyError) as exc_info:
        _start(frozenset({"PhotonBeam", "LiquidNitrogen"}), proc, context)
    assert exc_info.value.kind == "LiquidNitrogen"

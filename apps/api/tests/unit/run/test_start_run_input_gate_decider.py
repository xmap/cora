"""Decider tests for the genesis-only input-data gate on start_run.

Pins the gate that a reconstruction Run declaring `input_dataset_ids`
may not start unless EVERY declared input Dataset has at least one
Verified Distribution in `RunStartContext.input_distributions`:

  - input with a Verified Distribution -> passes
  - input with only a Stale / Registered Distribution -> RunInputNotVerifiedError
  - input with no Distribution at all -> RunInputNotVerifiedError
  - empty input_dataset_ids -> passes trivially (gate dormant)

The decider takes the context directly, so the stubs from the C1
port module are not needed here: the test constructs
`input_distributions` with seeded `DatasetDistributionLookupResult`
rows ("Verified" is the DistributionStatus.VERIFIED wire value).
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
from cora.infrastructure.ports.dataset_distribution_lookup import (
    DatasetDistributionLookupResult,
)
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import RunInputNotReachableError, RunInputNotVerifiedError
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 6, 25, 12, 0, 0, tzinfo=UTC)


def _distribution(
    dataset_id: UUID, status: str, *, supply_id: UUID | None = None
) -> DatasetDistributionLookupResult:
    return DatasetDistributionLookupResult(
        distribution_id=uuid4(),
        dataset_id=dataset_id,
        supply_id=supply_id if supply_id is not None else uuid4(),
        status=status,
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
    input_distributions: dict[UUID, tuple[DatasetDistributionLookupResult, ...]],
    *,
    reachable_storage_supply_ids: frozenset[UUID] | None = None,
) -> tuple[RunStartContext, frozenset[UUID]]:
    """Build a RunStartContext that passes every check EXCEPT possibly the
    input gate. Returns the context + the needed_family_ids the handler
    would resolve so the decider sees a satisfied Plan on every other
    dimension. `reachable_storage_supply_ids` defaults to None (the
    reachability arm is skipped, today's present-and-Verified behavior)."""
    cap = uuid4()
    asset_id = uuid4()
    plan = Plan(
        id=uuid4(),
        name=PlanName("Reconstruct"),
        practice_id=uuid4(),
        asset_ids=frozenset({asset_id}),
        status=PlanStatus.DEFINED,
    )
    asset = Asset(
        id=asset_id,
        name=AssetName("ComputeNode"),
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
        input_distributions=input_distributions,
        reachable_storage_supply_ids=reachable_storage_supply_ids,
    )
    return context, frozenset({cap})


def _start(
    input_dataset_ids: frozenset[UUID],
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
            input_dataset_ids=input_dataset_ids,
        ),
        context=context,
        needed_family_ids_snapshot=needed_family_ids,
        effective_parameters={},
        method_parameters_schema=None,
        now=_NOW,
        new_id=new_id,
    )


@pytest.mark.unit
def test_decide_passes_when_no_inputs_declared() -> None:
    """Empty input_dataset_ids short-circuits the gate (dormant feature)."""
    context, needs = _context(input_distributions={})
    decision = _start(frozenset(), context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_passes_when_input_has_a_verified_distribution() -> None:
    """A Verified Distribution satisfies the input gate; a Stale peer is irrelevant."""
    dataset_id = uuid4()
    context, needs = _context(
        input_distributions={
            dataset_id: (
                _distribution(dataset_id, "Stale"),
                _distribution(dataset_id, "Verified"),
            )
        }
    )
    decision = _start(frozenset({dataset_id}), context, uuid4(), needs)
    assert len(decision.run_events) == 1
    assert decision.run_events[0].input_dataset_ids == (dataset_id,)


@pytest.mark.unit
@pytest.mark.parametrize("status", ["Registered", "Stale"])
def test_decide_raises_when_input_has_no_verified_distribution(status: str) -> None:
    """Input with only a non-Verified Distribution -> RunInputNotVerifiedError."""
    dataset_id = uuid4()
    context, needs = _context(
        input_distributions={dataset_id: (_distribution(dataset_id, status),)}
    )
    new_id = uuid4()
    with pytest.raises(RunInputNotVerifiedError) as exc_info:
        _start(frozenset({dataset_id}), context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.dataset_id == dataset_id


@pytest.mark.unit
def test_decide_raises_when_input_has_no_distribution_at_all() -> None:
    """Declared input absent from the mapping -> RunInputNotVerifiedError."""
    dataset_id = uuid4()
    context, needs = _context(input_distributions={})
    new_id = uuid4()
    with pytest.raises(RunInputNotVerifiedError) as exc_info:
        _start(frozenset({dataset_id}), context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.dataset_id == dataset_id


@pytest.mark.unit
def test_decide_input_gate_diagnoses_first_failing_dataset_deterministically() -> None:
    """Multiple unsatisfied inputs: the decider raises for the first one in
    sorted iteration order so the operator-facing error is reproducible."""
    first = UUID("00000000-0000-0000-0000-000000000001")
    second = UUID("00000000-0000-0000-0000-000000000002")
    context, needs = _context(input_distributions={})
    with pytest.raises(RunInputNotVerifiedError) as exc_info:
        _start(frozenset({second, first}), context, uuid4(), needs)
    assert exc_info.value.dataset_id == first


@pytest.mark.unit
def test_decide_raises_for_the_unsatisfied_input_when_a_peer_input_is_verified() -> None:
    """Two declared inputs, one Verified and one Stale-only: the gate is a
    per-input universal quantifier, so the decider raises for the UNSATISFIED
    input even though its peer is satisfied."""
    verified_id = UUID("00000000-0000-0000-0000-0000000000a1")
    stale_id = UUID("00000000-0000-0000-0000-0000000000a2")
    context, needs = _context(
        input_distributions={
            verified_id: (_distribution(verified_id, "Verified"),),
            stale_id: (_distribution(stale_id, "Stale"),),
        }
    )
    new_id = uuid4()
    with pytest.raises(RunInputNotVerifiedError) as exc_info:
        _start(frozenset({verified_id, stale_id}), context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.dataset_id == stale_id


@pytest.mark.unit
def test_decide_passes_when_verified_distribution_is_on_a_reachable_tier() -> None:
    """Reachability arm: a Verified Distribution whose supply_id is in the
    reachable set lets the reconstruction start."""
    dataset_id = uuid4()
    reachable_tier = uuid4()
    context, needs = _context(
        input_distributions={
            dataset_id: (_distribution(dataset_id, "Verified", supply_id=reachable_tier),)
        },
        reachable_storage_supply_ids=frozenset({reachable_tier}),
    )
    decision = _start(frozenset({dataset_id}), context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_raises_not_reachable_when_verified_copy_is_on_an_unreachable_tier() -> None:
    """The motivating case: the input HAS a Verified Distribution but its
    supply_id is not in the reachable set -> RunInputNotReachableError (NOT
    RunInputNotVerifiedError)."""
    dataset_id = uuid4()
    context, needs = _context(
        input_distributions={
            dataset_id: (_distribution(dataset_id, "Verified", supply_id=uuid4()),)
        },
        reachable_storage_supply_ids=frozenset({uuid4()}),
    )
    new_id = uuid4()
    with pytest.raises(RunInputNotReachableError) as exc_info:
        _start(frozenset({dataset_id}), context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.dataset_id == dataset_id


@pytest.mark.unit
def test_decide_skips_reachability_when_reachable_set_is_none() -> None:
    """None reachable set -> today's present-and-Verified behavior: a
    Verified-anywhere input starts regardless of which tier it rests on."""
    dataset_id = uuid4()
    context, needs = _context(
        input_distributions={
            dataset_id: (_distribution(dataset_id, "Verified", supply_id=uuid4()),)
        },
        reachable_storage_supply_ids=None,
    )
    decision = _start(frozenset({dataset_id}), context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_empty_reachable_set_fails_every_verified_input_closed() -> None:
    """Empty reachable set means the resource can read no tier, so a Verified
    input still fails reachability (fail-closed)."""
    dataset_id = uuid4()
    context, needs = _context(
        input_distributions={
            dataset_id: (_distribution(dataset_id, "Verified", supply_id=uuid4()),)
        },
        reachable_storage_supply_ids=frozenset(),
    )
    new_id = uuid4()
    with pytest.raises(RunInputNotReachableError) as exc_info:
        _start(frozenset({dataset_id}), context, new_id, needs)
    assert exc_info.value.dataset_id == dataset_id


@pytest.mark.unit
def test_decide_not_verified_takes_precedence_over_not_reachable() -> None:
    """An input with NO Verified Distribution + a non-empty reachable set
    raises RunInputNotVerifiedError, not RunInputNotReachableError."""
    dataset_id = uuid4()
    context, needs = _context(
        input_distributions={dataset_id: (_distribution(dataset_id, "Stale"),)},
        reachable_storage_supply_ids=frozenset({uuid4()}),
    )
    with pytest.raises(RunInputNotVerifiedError):
        _start(frozenset({dataset_id}), context, uuid4(), needs)


@pytest.mark.unit
def test_decide_mixed_inputs_raises_not_reachable_for_the_unreachable_one() -> None:
    """One input reachable, one Verified-but-unreachable: the gate raises
    RunInputNotReachableError for the unreachable input, deterministically by
    sorted dataset_id."""
    reachable_id = UUID("00000000-0000-0000-0000-0000000000b1")
    unreachable_id = UUID("00000000-0000-0000-0000-0000000000b2")
    reachable_tier = uuid4()
    context, needs = _context(
        input_distributions={
            reachable_id: (_distribution(reachable_id, "Verified", supply_id=reachable_tier),),
            unreachable_id: (_distribution(unreachable_id, "Verified", supply_id=uuid4()),),
        },
        reachable_storage_supply_ids=frozenset({reachable_tier}),
    )
    new_id = uuid4()
    with pytest.raises(RunInputNotReachableError) as exc_info:
        _start(frozenset({reachable_id, unreachable_id}), context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.dataset_id == unreachable_id

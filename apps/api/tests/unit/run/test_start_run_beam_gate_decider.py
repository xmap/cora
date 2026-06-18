"""Decider tests for the cross-BC beam-availability pre-flight gate on start_run.

Pins the BEAM-1 gate truth table:
  - `beam_availability is None` skips the gate (beam-by-default for
    deployments that configure no beam PVs).
  - `quality_ok=False` fails closed -> `RunBeamAvailabilityUnknownError`
    (a dead gateway must never read as "beam open").
  - any of `fes_open` / `sbs_open` / `fes_permit` False (with good
    quality) -> `RunRequiresOpenBeamShuttersError`, with `blocking`
    naming each failing flag.
  - all flags True passes.

The Unknown check is ordered before the open check, so a bad-quality
read raises Unknown even when the (untrustworthy) flags read closed.
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
from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.recipe.aggregates.plan import Plan, PlanName, PlanStatus
from cora.run.aggregates.run import (
    RunBeamAvailabilityUnknownError,
    RunRequiresOpenBeamShuttersError,
)
from cora.run.features import start_run
from cora.run.features.start_run import RunStartContext, StartRun
from cora.subject.aggregates.subject import Subject, SubjectName, SubjectStatus

_NOW = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _beam(
    *,
    fes_open: bool = True,
    sbs_open: bool = True,
    fes_permit: bool = True,
    quality_ok: bool = True,
) -> BeamAvailabilityLookupResult:
    return BeamAvailabilityLookupResult(
        fes_open=fes_open,
        sbs_open=sbs_open,
        fes_permit=fes_permit,
        quality_ok=quality_ok,
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
    beam_availability: BeamAvailabilityLookupResult | None,
) -> tuple[RunStartContext, frozenset[UUID]]:
    """Build a RunStartContext that passes every check EXCEPT possibly
    the beam gate. Returns the context + the needed_family_ids the
    handler would resolve so the decider sees a satisfied Plan on the
    non-beam dimensions."""
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
        beam_availability=beam_availability,
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
def test_decide_passes_when_beam_availability_is_none() -> None:
    """None skips the gate (beam-by-default, no beam PVs configured)."""
    context, needs = _context(beam_availability=None)
    decision = _start(context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_passes_when_all_flags_open_and_quality_good() -> None:
    context, needs = _context(beam_availability=_beam())
    decision = _start(context, uuid4(), needs)
    assert len(decision.run_events) == 1


@pytest.mark.unit
def test_decide_raises_unknown_when_quality_not_ok() -> None:
    """Fail-closed: bad-quality read -> Unknown, regardless of flags."""
    context, needs = _context(
        beam_availability=_beam(fes_open=True, sbs_open=True, quality_ok=False)
    )
    new_id = uuid4()
    with pytest.raises(RunBeamAvailabilityUnknownError) as exc_info:
        _start(context, new_id, needs)
    assert exc_info.value.run_id == new_id


@pytest.mark.unit
def test_decide_unknown_takes_precedence_over_closed_shutters() -> None:
    """A bad-quality read with closed flags still raises Unknown, not
    RequiresOpenBeamShutters: the flags are untrustworthy."""
    context, needs = _context(
        beam_availability=_beam(fes_open=False, sbs_open=False, quality_ok=False)
    )
    with pytest.raises(RunBeamAvailabilityUnknownError):
        _start(context, uuid4(), needs)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kwargs", "expected_flag"),
    [
        ({"fes_open": False}, "fes_open"),
        ({"sbs_open": False}, "sbs_open"),
        ({"fes_permit": False}, "fes_permit"),
    ],
)
def test_decide_raises_requires_open_when_one_flag_closed(
    kwargs: dict[str, bool], expected_flag: str
) -> None:
    context, needs = _context(beam_availability=_beam(**kwargs))
    new_id = uuid4()
    with pytest.raises(RunRequiresOpenBeamShuttersError) as exc_info:
        _start(context, new_id, needs)
    assert exc_info.value.run_id == new_id
    assert exc_info.value.blocking == frozenset({expected_flag})


@pytest.mark.unit
def test_decide_blocking_names_every_closed_flag() -> None:
    context, needs = _context(
        beam_availability=_beam(fes_open=False, sbs_open=False, fes_permit=False)
    )
    with pytest.raises(RunRequiresOpenBeamShuttersError) as exc_info:
        _start(context, uuid4(), needs)
    assert exc_info.value.blocking == frozenset({"fes_open", "sbs_open", "fes_permit"})

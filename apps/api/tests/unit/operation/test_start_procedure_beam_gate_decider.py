"""Decider tests for the cross-BC beam-availability gate on start_procedure.

Mirror of start_run's beam gate test. Pins the BEAM-1 truth table:
  - `beam_availability is None` skips the gate (beam-by-default).
  - `quality_ok=False` fails closed
    -> `ProcedureBeamAvailabilityUnknownError`.
  - any of `fes_open` / `sbs_open` / `fes_permit` False (good quality)
    -> `ProcedureRequiresOpenBeamShuttersError`, naming each flag.
  - all flags True passes.

Unknown is checked before the open check, so a bad-quality read raises
Unknown even with closed (untrustworthy) flags.
"""

import dataclasses
from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.ports.beam_availability_lookup import (
    BeamAvailabilityLookupResult,
    BeamState,
)
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureBeamAvailabilityUnknownError,
    ProcedureName,
    ProcedureRequiresOpenBeamShuttersError,
    ProcedureRequiresPermittedEnclosureError,
    ProcedureStatus,
)
from cora.operation.features import start_procedure
from cora.operation.features.start_procedure import ProcedureStartContext, StartProcedure
from cora.shared.beam_requirement import BeamRequirement

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


def _procedure() -> Procedure:
    return Procedure(
        id=UUID("00000000-0000-0000-0000-0000000000aa"),
        name=ProcedureName("Bakeout"),
        kind="bakeout",
        target_asset_ids=frozenset(),
        status=ProcedureStatus.DEFINED,
    )


def _context(beam_availability: BeamAvailabilityLookupResult | None) -> ProcedureStartContext:
    return ProcedureStartContext(assets={}, beam_availability=beam_availability)


def _start(procedure: Procedure, context: ProcedureStartContext):
    return start_procedure.decide(
        state=procedure,
        command=StartProcedure(procedure_id=procedure.id),
        context=context,
        now=_NOW,
    )


@pytest.mark.unit
def test_decide_passes_when_beam_availability_is_none() -> None:
    """None skips the gate (beam-by-default, no beam PVs configured)."""
    decision = _start(_procedure(), _context(beam_availability=None))
    assert len(decision) == 1


@pytest.mark.unit
def test_decide_passes_when_all_flags_open_and_quality_good() -> None:
    decision = _start(_procedure(), _context(beam_availability=_beam()))
    assert len(decision) == 1


@pytest.mark.unit
def test_decide_raises_unknown_when_quality_not_ok() -> None:
    procedure = _procedure()
    with pytest.raises(ProcedureBeamAvailabilityUnknownError) as exc_info:
        _start(procedure, _context(beam_availability=_beam(quality_ok=False)))
    assert exc_info.value.procedure_id == procedure.id


@pytest.mark.unit
def test_decide_unknown_takes_precedence_over_closed_shutters() -> None:
    procedure = _procedure()
    with pytest.raises(ProcedureBeamAvailabilityUnknownError):
        _start(
            procedure,
            _context(beam_availability=_beam(fes_open=False, sbs_open=False, quality_ok=False)),
        )


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
    procedure = _procedure()
    with pytest.raises(ProcedureRequiresOpenBeamShuttersError) as exc_info:
        _start(procedure, _context(beam_availability=_beam(**kwargs)))
    assert exc_info.value.procedure_id == procedure.id
    assert exc_info.value.blocking == frozenset({expected_flag})


@pytest.mark.unit
def test_decide_blocking_names_every_closed_flag() -> None:
    procedure = _procedure()
    with pytest.raises(ProcedureRequiresOpenBeamShuttersError) as exc_info:
        _start(
            procedure,
            _context(beam_availability=_beam(fes_open=False, sbs_open=False, fes_permit=False)),
        )
    assert exc_info.value.blocking == frozenset({"fes_open", "sbs_open", "fes_permit"})


# ----- BeamRequirement.NOT_REQUIRED: the off-beam exemption -----
#
# The gate above refuses every start without beam. That is right for a
# measurement and wrong for work defined by beam's absence (a dark field
# closes the shutter as its first step) or indifferent to it (a hexapod
# power-cycle). It is also wrong for the window that matters most:
# commissioning happens only between user operations, when there is no
# beam, so a blanket refusal refuses the entire commissioning period.


def _exempt_procedure() -> Procedure:
    return Procedure(
        id=UUID("00000000-0000-0000-0000-0000000000bb"),
        name=ProcedureName("Dark field"),
        kind="dark_field",
        target_asset_ids=frozenset(),
        status=ProcedureStatus.DEFINED,
        beam_requirement=BeamRequirement.NOT_REQUIRED,
    )


@pytest.mark.unit
def test_not_required_procedure_starts_with_every_beam_flag_closed() -> None:
    """The exemption's whole purpose: the 2-BM commissioning state
    (ring empty, both shutters closed, no FES permit) must start."""
    procedure = _exempt_procedure()
    events = _start(
        procedure,
        _context(beam_availability=_beam(fes_open=False, sbs_open=False, fes_permit=False)),
    )
    assert [type(e).__name__ for e in events] == ["ProcedureStarted"]


@pytest.mark.unit
def test_not_required_procedure_starts_when_beam_read_quality_is_bad() -> None:
    """Fail-closed applies to the REFUSAL, not to the exemption: an
    execution that does not care about beam does not care that the read
    failed either. The observation still records UNKNOWN."""
    procedure = _exempt_procedure()
    events = _start(procedure, _context(beam_availability=_beam(quality_ok=False)))
    assert [type(e).__name__ for e in events] == ["ProcedureStarted"]
    assert events[0].beam_state_at_start is BeamState.UNKNOWN


@pytest.mark.unit
def test_required_procedure_still_refuses_when_beam_is_blocked() -> None:
    """The default is unchanged. Pinned beside the exemption so a future
    edit cannot widen the skip to every Procedure without going red."""
    procedure = _procedure()
    assert procedure.beam_requirement is BeamRequirement.REQUIRED
    with pytest.raises(ProcedureRequiresOpenBeamShuttersError):
        _start(procedure, _context(beam_availability=_beam(sbs_open=False)))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("requirement", "beam", "expected_state"),
    [
        (BeamRequirement.REQUIRED, _beam(), BeamState.OPEN),
        (BeamRequirement.NOT_REQUIRED, _beam(), BeamState.OPEN),
        (BeamRequirement.NOT_REQUIRED, _beam(sbs_open=False), BeamState.BLOCKED),
        (BeamRequirement.NOT_REQUIRED, _beam(quality_ok=False), BeamState.UNKNOWN),
        (BeamRequirement.NOT_REQUIRED, None, None),
    ],
)
def test_start_event_records_what_beam_looked_like_either_way(
    requirement: BeamRequirement,
    beam: BeamAvailabilityLookupResult | None,
    expected_state: BeamState | None,
) -> None:
    """A skipped gate must not be a silent gate.

    Without this the record cannot separate "started while beam happened
    to be available" from "started with no beam under a declared
    exemption", and an auditor reading the published record afterwards
    has no way to tell which occurred.
    """
    procedure = dataclasses.replace(_procedure(), beam_requirement=requirement)
    events = _start(procedure, _context(beam_availability=beam))
    assert events[0].beam_requirement is requirement
    assert events[0].beam_state_at_start is expected_state


@pytest.mark.unit
def test_not_required_does_not_relax_the_enclosure_gate() -> None:
    """The exemption is scoped to the BEAM arm alone.

    An unsearched hutch is no less disqualifying because the work needs
    no beam, and this is the assertion that stops a future refactor from
    turning one narrow exemption into a general pre-flight bypass.
    """
    procedure = _exempt_procedure()
    context = ProcedureStartContext(
        assets={},
        beam_availability=_beam(fes_open=False, sbs_open=False, fes_permit=False),
        referencing_enclosures=(
            EnclosureLookupResult(
                enclosure_id=UUID("00000000-0000-0000-0000-0000000000cc"),
                name="2-BM-B",
                permit_status="Denied",
                lifecycle="Active",
                permit_status_changed_at=_NOW.isoformat(),
                source_kind="EpicsPv",
                source_id="S02BM-PSS:StaB:SecureM",
            ),
        ),
    )
    with pytest.raises(ProcedureRequiresPermittedEnclosureError):
        _start(procedure, context)

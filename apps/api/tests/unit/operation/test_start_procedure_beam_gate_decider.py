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

from datetime import UTC, datetime
from uuid import UUID

import pytest

from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.operation.aggregates.procedure import (
    Procedure,
    ProcedureBeamAvailabilityUnknownError,
    ProcedureName,
    ProcedureRequiresOpenBeamShuttersError,
    ProcedureStatus,
)
from cora.operation.features import start_procedure
from cora.operation.features.start_procedure import ProcedureStartContext, StartProcedure

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

"""Unit tests for the shared start-safety-envelope check.

`check_safety_envelope` is the extracted core of the four cross-BC
live-signal gates (clearance / supply / enclosure / beam) shared by
`start_run` and the RunSupervisor's pre-resume re-check. These pin the
pass path and each failing gate so the two callers can rely on one
definition of "safe to (re)start".

The full-decider gate tests (`test_start_run_*_gate_decider.py`) remain
the guardrails proving the extraction is behavior-preserving; these add
focused coverage at the helper boundary.
"""

from collections.abc import Mapping
from uuid import UUID, uuid4

import pytest

from cora.infrastructure.ports.beam_availability_lookup import BeamAvailabilityLookupResult
from cora.infrastructure.ports.clearance_lookup import ClearanceLookupResult
from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult
from cora.infrastructure.ports.supply_lookup import SupplyLookupResult
from cora.run.aggregates.run import (
    RunBeamAvailabilityUnknownError,
    RunClearanceCoverageMismatchError,
    RunEnclosureCoverageMismatchError,
    RunRequiresActiveClearanceError,
    RunRequiresAvailableSupplyError,
    RunRequiresOpenBeamShuttersError,
    RunRequiresPermittedEnclosureError,
    RunSupplyCoverageMismatchError,
    check_safety_envelope,
)

_RUN_ID = UUID("01900000-0000-7000-8000-0000000005a1")


def _clearance(status: str) -> ClearanceLookupResult:
    return ClearanceLookupResult(
        clearance_id=uuid4(),
        status=status,
        template_id=uuid4(),
        template_code="ESAF",
        facility_code="cora",
    )


def _supply(status: str) -> SupplyLookupResult:
    return SupplyLookupResult(
        supply_id=uuid4(),
        kind="LN2",
        name="detector dewar",
        status=status,
        facility_code="cora",
    )


def _enclosure(permit_status: str, lifecycle: str) -> EnclosureLookupResult:
    return EnclosureLookupResult(
        enclosure_id=uuid4(),
        name="2-BM-A",
        permit_status=permit_status,
        lifecycle=lifecycle,
        observed_at=None,
        source_kind=None,
        source_id=None,
    )


def _beam(
    *,
    fes_open: bool = True,
    sbs_open: bool = True,
    fes_permit: bool = True,
    quality_ok: bool = True,
) -> BeamAvailabilityLookupResult:
    return BeamAvailabilityLookupResult(
        fes_open=fes_open, sbs_open=sbs_open, fes_permit=fes_permit, quality_ok=quality_ok
    )


def _check(
    *,
    referencing_clearances: tuple[ClearanceLookupResult, ...] | None = None,
    needed_supplies_snapshot: frozenset[str] | None = None,
    needed_supplies_satisfaction: Mapping[str, tuple[SupplyLookupResult, ...]] | None = None,
    referencing_enclosures: tuple[EnclosureLookupResult, ...] | None = None,
    beam_availability: BeamAvailabilityLookupResult | None = None,
) -> None:
    """Run the check against a fully-passing envelope; each kwarg overrides
    one dimension. Beam defaults to all-open (pass `_beam(...)` to fail it)."""
    check_safety_envelope(
        run_id=_RUN_ID,
        referencing_clearances=(
            referencing_clearances
            if referencing_clearances is not None
            else (_clearance("Active"),)
        ),
        needed_supplies_snapshot=(
            needed_supplies_snapshot if needed_supplies_snapshot is not None else frozenset({"LN2"})
        ),
        needed_supplies_satisfaction=(
            needed_supplies_satisfaction
            if needed_supplies_satisfaction is not None
            else {"LN2": (_supply("Available"),)}
        ),
        referencing_enclosures=(
            referencing_enclosures
            if referencing_enclosures is not None
            else (_enclosure("Permitted", "Active"),)
        ),
        beam_availability=beam_availability if beam_availability is not None else _beam(),
    )


@pytest.mark.unit
def test_full_envelope_passes_returns_none() -> None:
    assert _check() is None


@pytest.mark.unit
def test_empty_optional_dimensions_pass() -> None:
    """An Active clearance is the only hard requirement; empty enclosures is
    permit-by-default, empty needed-supplies skips the supply gate, and a
    None beam reading skips the beam gate."""
    assert (
        check_safety_envelope(
            run_id=_RUN_ID,
            referencing_clearances=(_clearance("Active"),),
            needed_supplies_snapshot=frozenset(),
            needed_supplies_satisfaction={},
            referencing_enclosures=(),
            beam_availability=None,
        )
        is None
    )


@pytest.mark.unit
def test_no_clearance_raises_requires_active() -> None:
    with pytest.raises(RunRequiresActiveClearanceError):
        _check(referencing_clearances=())


@pytest.mark.unit
def test_clearance_present_but_none_active_raises_coverage_mismatch() -> None:
    with pytest.raises(RunClearanceCoverageMismatchError):
        _check(referencing_clearances=(_clearance("Expired"), _clearance("Superseded")))


@pytest.mark.unit
def test_needed_supply_kind_absent_raises_requires_available() -> None:
    with pytest.raises(RunRequiresAvailableSupplyError):
        _check(needed_supplies_satisfaction={})


@pytest.mark.unit
def test_supply_present_but_none_available_raises_coverage_mismatch() -> None:
    with pytest.raises(RunSupplyCoverageMismatchError):
        _check(needed_supplies_satisfaction={"LN2": (_supply("Degraded"),)})


@pytest.mark.unit
def test_all_enclosures_fail_raises_requires_permitted() -> None:
    with pytest.raises(RunRequiresPermittedEnclosureError):
        _check(referencing_enclosures=(_enclosure("NotPermitted", "Active"),))


@pytest.mark.unit
def test_mixed_enclosures_raise_coverage_mismatch() -> None:
    with pytest.raises(RunEnclosureCoverageMismatchError):
        _check(
            referencing_enclosures=(
                _enclosure("Permitted", "Active"),
                _enclosure("NotPermitted", "Active"),
            )
        )


@pytest.mark.unit
def test_beam_unknown_quality_raises_availability_unknown() -> None:
    with pytest.raises(RunBeamAvailabilityUnknownError):
        _check(beam_availability=_beam(quality_ok=False))


@pytest.mark.unit
def test_closed_shutter_raises_requires_open_shutters() -> None:
    with pytest.raises(RunRequiresOpenBeamShuttersError):
        _check(beam_availability=_beam(sbs_open=False))

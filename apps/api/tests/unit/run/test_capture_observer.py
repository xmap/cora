"""Unit tests for the `CaptureObserver` port and its `QuietCaptureObserver` stub.

Mirrors `test_enclosure_observer.py`'s shape, adjusted for the one real
difference between the two ports: there is no safe "always" reading for
a capture phase the way `AlwaysPermittedEnclosureObserver` has one for a
permit status, so the stub here yields nothing rather than one
observation per code.
"""

from datetime import UTC, datetime

import pytest

from cora.run.ports.capture_observer import (
    CaptureLifecycleObservation,
    CaptureObserver,
    CaptureObserverScope,
    CapturePhase,
    QuietCaptureObserver,
)
from cora.shared.reach import ReachTier

_TOMOSCAN = "2bmb-tomoscan"
_OTHER = "2bmb-tomoscan-alt"
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


@pytest.mark.unit
def test_quiet_observer_satisfies_capture_observer_protocol() -> None:
    assert isinstance(QuietCaptureObserver(), CaptureObserver)


@pytest.mark.unit
async def test_quiet_observer_yields_nothing_for_empty_scope() -> None:
    observer = QuietCaptureObserver()
    scope = CaptureObserverScope(capture_codes=frozenset())
    observations = [obs async for obs in observer.observe(scope)]
    assert observations == []


@pytest.mark.unit
async def test_quiet_observer_yields_nothing_for_a_populated_scope() -> None:
    """Unlike the Enclosure stub's optimistic default, there is no safe
    'always' capture phase, so a populated scope still yields nothing
    rather than a synthesized reading."""
    observer = QuietCaptureObserver()
    scope = CaptureObserverScope(capture_codes=frozenset({_TOMOSCAN, _OTHER}))
    observations = [obs async for obs in observer.observe(scope)]
    assert observations == []


@pytest.mark.unit
def test_capture_observation_is_frozen_dataclass() -> None:
    obs = CaptureLifecycleObservation(
        capture_code=_TOMOSCAN,
        reported_status="Scan complete",
        phase=CapturePhase.ENDED,
        reach_tier=ReachTier.RELAYED,
        observed_at=_EPOCH,
        source_kind="EpicsPv",
        source_id="2bmb:TomoScan:ScanStatus",
    )
    with pytest.raises(AttributeError):
        obs.phase = CapturePhase.BEGUN  # type: ignore[misc]


@pytest.mark.unit
def test_capture_observer_scope_is_frozen_dataclass() -> None:
    scope = CaptureObserverScope(capture_codes=frozenset({_TOMOSCAN}))
    with pytest.raises(AttributeError):
        scope.capture_codes = frozenset({_OTHER})  # type: ignore[misc]


@pytest.mark.unit
def test_capture_observation_permits_a_probe_only_reading_with_no_phase() -> None:
    """A probe-only re-affirmation carries no status claim and therefore
    no phase, mirroring `EnclosureObservation.observed_status=None`."""
    obs = CaptureLifecycleObservation(
        capture_code=_TOMOSCAN,
        reported_status=None,
        phase=None,
        reach_tier=ReachTier.RELAYED,
        observed_at=None,
        source_kind="EpicsPv",
        source_id="2bmb:TomoScan:ScanStatus",
    )
    assert obs.reported_status is None
    assert obs.phase is None


@pytest.mark.unit
def test_capture_phase_has_an_unrecognized_member_for_vocabulary_drift() -> None:
    """A substrate literal that does not match the deployment's declared
    mapping must classify as UNRECOGNIZED, never be dropped or coerced
    into a nearby phase."""
    assert CapturePhase.UNRECOGNIZED in CapturePhase
    assert CapturePhase.UNRECOGNIZED.value == "Unrecognized"

"""Tests for the RunWatcher shadow runtime (cora.api._run_watcher).

Covers the no-op-when-unconfigured lifespan shape, that every observed
phase (and the two no-phase cases, unreached and probe-only) logs the
right event with the right fields, that a bad observation is logged
and skipped rather than killing the loop, and that a stream ending
triggers reconnect rather than the loop exiting silently.

Every assertion is against `structlog.testing.capture_logs()`. There is
nothing else to assert: shadow mode has no event store, no entries
table, and no Run command, so "it wrote nothing" is a structural fact
about the module's imports, not a per-test behavior to pin.
"""

# white-box test of the runtime internals (private constants)
# pyright: reportPrivateUsage=false

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import structlog.testing

from cora.api._run_watcher import observe_capture, run_run_watcher, run_watcher_lifespan
from cora.run.ports.capture_observer import CaptureObservation, CaptureObserverScope, CapturePhase
from cora.shared.reach import ReachTier

_CODE = "2bmb-tomoscan"
_NOW = datetime(2026, 8, 13, 12, 0, 0, tzinfo=UTC)


def _obs(
    *,
    reported_status: str | None,
    phase: CapturePhase | None,
    reach_tier: ReachTier = ReachTier.RELAYED,
    observed_at: datetime | None = _NOW,
    capture_code: str = _CODE,
) -> CaptureObservation:
    return CaptureObservation(
        capture_code=capture_code,
        reported_status=reported_status,
        phase=phase,
        reach_tier=reach_tier,
        observed_at=observed_at,
        source_kind="EpicsPv",
        source_id="2bmb:TomoScan:ScanStatus",
    )


class _FakeObserver:
    """Yields a fixed observation sequence once, then ends the stream."""

    def __init__(self, observations: list[CaptureObservation]) -> None:
        self._observations = observations

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[CaptureObservation]:
        for observation in self._observations:
            yield observation


class _BoomObserver:
    """Raises mid-iteration so the loop's outer resilience branch fires."""

    def observe(self, scope: CaptureObserverScope) -> AsyncGenerator[CaptureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[CaptureObservation]:
        raise RuntimeError("observer boom")
        yield  # pragma: no cover - unreachable, marks this body an async generator


@pytest.mark.unit
@pytest.mark.parametrize(
    ("phase", "expected_event"),
    [
        (CapturePhase.BEGUN, "run_watcher.capture_begun"),
        (CapturePhase.PROGRESSING, "run_watcher.capture_progressing"),
        (CapturePhase.ENDED, "run_watcher.capture_ended"),
        (CapturePhase.ABORTED, "run_watcher.capture_aborted"),
        (CapturePhase.UNRECOGNIZED, "run_watcher.capture_unrecognized"),
    ],
)
def test_observe_capture_logs_the_matching_event_per_phase(
    phase: CapturePhase, expected_event: str
) -> None:
    with structlog.testing.capture_logs() as logs:
        observe_capture(_obs(reported_status="whatever", phase=phase))
    assert [entry["event"] for entry in logs] == [expected_event]


@pytest.mark.unit
def test_observe_capture_logs_unreached_for_a_probe_only_observation() -> None:
    """A `None` phase (no status claim at all) logs as unreached rather
    than being silently dropped."""
    with structlog.testing.capture_logs() as logs:
        observe_capture(_obs(reported_status=None, phase=None))
    assert [entry["event"] for entry in logs] == ["run_watcher.capture_unreached"]


@pytest.mark.unit
def test_observe_capture_carries_the_full_attribution() -> None:
    with structlog.testing.capture_logs() as logs:
        observe_capture(_obs(reported_status="Scan complete", phase=CapturePhase.ENDED))
    entry = logs[0]
    assert entry["capture_code"] == _CODE
    assert entry["reported_status"] == "Scan complete"
    assert entry["source_kind"] == "EpicsPv"
    assert entry["source_id"] == "2bmb:TomoScan:ScanStatus"
    assert entry["observed_at"] == _NOW.isoformat()


@pytest.mark.unit
def test_observe_capture_reports_no_substrate_time_as_none_not_a_string() -> None:
    """An adapter with no substrate time reports `None`; the log line
    must carry that faithfully rather than stringifying a sentinel."""
    with structlog.testing.capture_logs() as logs:
        observe_capture(
            _obs(reported_status="Scan complete", phase=CapturePhase.ENDED, observed_at=None)
        )
    assert logs[0]["observed_at"] is None


@pytest.mark.unit
async def test_run_run_watcher_is_a_no_op_for_empty_capture_codes() -> None:
    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    await run_run_watcher(observer=observer, capture_codes=frozenset())
    # No assertion needed beyond "returns": an observer never drained
    # would hang forever if the empty-scope short-circuit were missing.


@pytest.mark.unit
async def test_run_run_watcher_logs_every_observation_in_sequence() -> None:
    observer = _FakeObserver(
        [
            _obs(reported_status="Beginning scan", phase=CapturePhase.BEGUN),
            _obs(reported_status="Collecting projections", phase=CapturePhase.PROGRESSING),
            _obs(reported_status="Scan complete", phase=CapturePhase.ENDED),
        ]
    )
    task = asyncio.create_task(run_run_watcher(observer=observer, capture_codes=frozenset({_CODE})))
    with structlog.testing.capture_logs() as logs:
        await asyncio.sleep(0.05)  # one full drain of the fixed sequence
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    events = [entry["event"] for entry in logs]
    assert events == [
        "run_watcher.capture_begun",
        "run_watcher.capture_progressing",
        "run_watcher.capture_ended",
    ]


@pytest.mark.unit
async def test_run_run_watcher_survives_an_observer_that_raises() -> None:
    """The outer resilience branch logs and reconnects rather than the
    loop propagating the exception and dying silently."""
    task = asyncio.create_task(
        run_run_watcher(
            observer=_BoomObserver(),
            capture_codes=frozenset({_CODE}),
            reconnect_delay_seconds=0.01,
        )
    )
    with structlog.testing.capture_logs() as logs:
        await asyncio.sleep(0.05)  # several reconnect passes at this cadence
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    events = [entry["event"] for entry in logs]
    assert "run_watcher.iteration_failed" in events


@pytest.mark.unit
async def test_lifespan_is_a_no_op_when_no_capture_codes_configured() -> None:
    entered = False
    async with run_watcher_lifespan(observer=_FakeObserver([]), capture_codes=frozenset()):
        entered = True
    assert entered


@pytest.mark.unit
async def test_lifespan_spawns_and_cleanly_cancels_the_background_task() -> None:
    observer = _FakeObserver([_obs(reported_status="Scan complete", phase=CapturePhase.ENDED)])
    with structlog.testing.capture_logs() as logs:
        async with run_watcher_lifespan(observer=observer, capture_codes=frozenset({_CODE})):
            await asyncio.sleep(0.02)
    events = [entry["event"] for entry in logs]
    assert "run_watcher.capture_ended" in events

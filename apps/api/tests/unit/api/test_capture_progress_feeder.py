"""Unit tests for `CaptureProgressFeeder` (cora.api._capture_progress_feeder).

Covers the decimating buffer (latest-wins per capture_code/role), the
per-code flush contract (one AppendObservations batch + one heartbeat,
independently), the no-open-Run drop, the no-substrate-time skip, and
that a failure on one write path (UnauthorizedError,
RunObservationLogbookClosedError, a bare exception) never suppresses
the other.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.api._capture_progress_feeder import CaptureProgressFeeder
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import (
    FeedHeartbeat,
    InMemoryFeedHeartbeatStore,
    RunObservationLogbookClosedError,
    RunStatus,
)
from cora.run.errors import UnauthorizedError
from cora.run.features.append_observations.command import AppendObservations
from cora.run.ports.capture_observer import CaptureProgressObservation
from cora.shared.reach import ReachTier
from tests.unit._helpers import build_deps

_CODE = "2bmb-tomoscan"
_NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)
_RUN_ID = UUID("01900000-0000-7000-8000-000000007101")
_PRINCIPAL_ID = uuid4()


def _reading(
    *,
    role: str = "images_saved",
    value: float = 1.0,
    observed_at: datetime | None = _NOW,
    capture_code: str = _CODE,
) -> CaptureProgressObservation:
    return CaptureProgressObservation(
        capture_code=capture_code,
        role=role,
        value=value,
        reach_tier=ReachTier.RELAYED,
        observed_at=observed_at,
        source_kind="EpicsPv",
        source_id=f"2bmb:TomoScan:{role}",
    )


class _FakeAppendObservations:
    """Records every call; raises the scripted error, if any, when called."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[AppendObservations] = []
        self._raises = raises

    async def __call__(
        self,
        command: AppendObservations,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        causation_id: UUID | None = None,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> int:
        if self._raises is not None:
            raise self._raises
        self.calls.append(command)
        return len(command.entries)


def _feeder(
    *,
    append_observations: _FakeAppendObservations | None = None,
    heartbeat_store: InMemoryFeedHeartbeatStore | None = None,
    open_run_id: UUID | None = _RUN_ID,
) -> tuple[CaptureProgressFeeder, _FakeAppendObservations, InMemoryFeedHeartbeatStore]:
    append = append_observations if append_observations is not None else _FakeAppendObservations()
    heartbeats = heartbeat_store if heartbeat_store is not None else InMemoryFeedHeartbeatStore()
    feeder = CaptureProgressFeeder(
        deps=build_deps(ids=[uuid4() for _ in range(50)], now=_NOW),
        append_observations=append,  # type: ignore[arg-type]
        feed_heartbeat_store=heartbeats,
        open_run_id_for=lambda _code: open_run_id,
        principal_id=_PRINCIPAL_ID,
    )
    return feeder, append, heartbeats


@pytest.mark.unit
async def test_flush_capture_with_nothing_buffered_writes_nothing() -> None:
    feeder, append, heartbeats = _feeder()

    await feeder.flush_capture(_CODE)

    assert append.calls == []
    assert heartbeats.all() == []


@pytest.mark.unit
async def test_offer_then_flush_writes_one_observation_per_channel() -> None:
    feeder, append, _ = _feeder()
    feeder.offer(_reading(role="images_saved", value=3.0))
    feeder.offer(_reading(role="images_collected", value=5.0))

    await feeder.flush_capture(_CODE)

    assert len(append.calls) == 1
    command = append.calls[0]
    assert command.run_id == _RUN_ID
    channels = {(e.channel_name, e.value) for e in command.entries}
    assert channels == {("images_saved", 3.0), ("images_collected", 5.0)}
    assert all(e.sampling_procedure == "monitor" for e in command.entries)
    assert all(e.units is None for e in command.entries)
    assert all(e.is_simulated is False for e in command.entries)


@pytest.mark.unit
async def test_offer_twice_for_the_same_role_keeps_only_the_latest_value() -> None:
    """Decimation: the buffer is latest-wins per (capture_code, role), so
    a burst of readings between flushes costs one dict assignment and
    the flush sees only the last one."""
    feeder, append, _ = _feeder()
    for value in (0.0, 3.0, 7.0, 11.0, 14.0):
        feeder.offer(_reading(role="images_saved", value=value))

    await feeder.flush_capture(_CODE)

    assert len(append.calls) == 1
    assert len(append.calls[0].entries) == 1
    assert append.calls[0].entries[0].value == 14.0


@pytest.mark.unit
async def test_flush_capture_writes_a_heartbeat_even_with_nothing_buffered_for_it() -> None:
    """A code with an open Run but no buffered reading still gets a
    heartbeat once offer() has put SOMETHING in the buffer for it (the
    coverage-evidence contract): the heartbeat and the observation
    write are independent, not gated on each other."""
    feeder, append, heartbeats = _feeder()
    feeder.offer(_reading(role="images_saved", value=1.0))

    await feeder.flush_capture(_CODE)

    assert len(heartbeats.all()) == 1
    heartbeat: FeedHeartbeat = heartbeats.all()[0]
    assert heartbeat.run_id == _RUN_ID
    assert len(append.calls) == 1


@pytest.mark.unit
async def test_flush_with_no_open_run_drops_the_buffer_and_writes_nothing() -> None:
    feeder, append, heartbeats = _feeder(open_run_id=None)
    feeder.offer(_reading())

    await feeder.flush_capture(_CODE)

    assert append.calls == []
    assert heartbeats.all() == []


@pytest.mark.unit
async def test_flush_after_dropping_for_no_open_run_the_buffer_stays_empty() -> None:
    """The buffer is popped unconditionally before resolving run_id, so a
    dropped capture does not accumulate readings forever."""
    feeder, append, _ = _feeder(open_run_id=None)
    feeder.offer(_reading())
    await feeder.flush_capture(_CODE)

    await feeder.flush_capture(_CODE)

    assert append.calls == []


@pytest.mark.unit
async def test_offer_a_reading_with_no_substrate_time_is_skipped_not_synthesized() -> None:
    """The port's dual-clock rule forbids substituting CORA's own clock
    for an absent substrate time; a `None` observed_at is skipped."""
    feeder, append, heartbeats = _feeder()
    feeder.offer(_reading(role="images_saved", observed_at=None))
    feeder.offer(_reading(role="images_collected", observed_at=_NOW))

    await feeder.flush_capture(_CODE)

    assert len(append.calls) == 1
    assert [e.channel_name for e in append.calls[0].entries] == ["images_collected"]
    # The heartbeat still fires: the code had an open Run and a
    # (partially unusable) reading was buffered for it.
    assert len(heartbeats.all()) == 1


@pytest.mark.unit
async def test_offer_readings_all_with_no_substrate_time_writes_no_observations() -> None:
    feeder, append, heartbeats = _feeder()
    feeder.offer(_reading(observed_at=None))

    await feeder.flush_capture(_CODE)

    assert append.calls == []
    assert len(heartbeats.all()) == 1


@pytest.mark.unit
async def test_flush_survives_an_unauthorized_append_and_still_heartbeats() -> None:
    feeder, _append, heartbeats = _feeder(
        append_observations=_FakeAppendObservations(raises=UnauthorizedError("denied"))
    )
    feeder.offer(_reading())

    await feeder.flush_capture(_CODE)

    assert len(heartbeats.all()) == 1


@pytest.mark.unit
async def test_flush_survives_a_closed_logbook_and_still_heartbeats() -> None:
    feeder, _append, heartbeats = _feeder(
        append_observations=_FakeAppendObservations(
            raises=RunObservationLogbookClosedError(_RUN_ID, RunStatus.COMPLETED)
        )
    )
    feeder.offer(_reading())

    await feeder.flush_capture(_CODE)

    assert len(heartbeats.all()) == 1


@pytest.mark.unit
async def test_flush_survives_an_unexpected_append_exception_and_still_heartbeats() -> None:
    feeder, _append, heartbeats = _feeder(
        append_observations=_FakeAppendObservations(raises=RuntimeError("boom"))
    )
    feeder.offer(_reading())

    await feeder.flush_capture(_CODE)

    assert len(heartbeats.all()) == 1


@pytest.mark.unit
async def test_flush_only_touches_its_own_capture_codes_buffer() -> None:
    feeder, append, _ = _feeder()
    feeder.offer(_reading(capture_code="tomoscan-a", role="images_saved", value=1.0))
    feeder.offer(_reading(capture_code="tomoscan-b", role="images_saved", value=2.0))

    await feeder.flush_capture("tomoscan-a")

    assert len(append.calls) == 1
    assert append.calls[0].run_id == _RUN_ID
    assert [e.value for e in append.calls[0].entries] == [1.0]


@pytest.mark.unit
async def test_flush_flushes_every_buffered_capture_code() -> None:
    feeder, append, heartbeats = _feeder()
    feeder.offer(_reading(capture_code="tomoscan-a", role="images_saved", value=1.0))
    feeder.offer(_reading(capture_code="tomoscan-b", role="images_saved", value=2.0))

    await feeder.flush()

    assert len(append.calls) == 2
    assert len(heartbeats.all()) == 2

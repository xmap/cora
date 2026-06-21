"""Unit tests for the RunChannelLookup read port (in-memory stub).

The stub is the contract the PostgresRunChannelLookup adapter mirrors:
latest keys on recorded_at, an unseeded channel reads None (cannot-tell),
the window counts arrivals strictly after the `since` floor and OR-folds
is_simulated. The Postgres parity is covered in the integration suite.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from cora.run.ports import InMemoryRunChannelLookup

_RUN = uuid4()
_T0 = datetime(2026, 6, 21, 12, 0, 0, tzinfo=UTC)


def _at(seconds: int) -> datetime:
    return _T0 + timedelta(seconds=seconds)


@pytest.mark.unit
async def test_read_latest_returns_none_when_channel_never_produced() -> None:
    """An unseeded channel is the cannot-tell case the decider defers on."""
    lookup = InMemoryRunChannelLookup()
    assert await lookup.read_run_channel_latest(run_id=_RUN, channel_name="snr") is None


@pytest.mark.unit
async def test_read_latest_returns_most_recent_by_recorded_at() -> None:
    """Latest keys on recorded_at, not insertion order or sampled_at."""
    lookup = InMemoryRunChannelLookup()
    lookup.register(run_id=_RUN, channel_name="snr", value=4.0, recorded_at=_at(30))
    lookup.register(run_id=_RUN, channel_name="snr", value=9.0, recorded_at=_at(10))
    latest = await lookup.read_run_channel_latest(run_id=_RUN, channel_name="snr")
    assert latest is not None
    assert latest.value == 4.0
    assert latest.recorded_at == _at(30)


@pytest.mark.unit
async def test_read_latest_surfaces_is_simulated_and_units() -> None:
    lookup = InMemoryRunChannelLookup()
    lookup.register(
        run_id=_RUN,
        channel_name="snr",
        value=7.0,
        recorded_at=_at(5),
        units="dB",
        is_simulated=True,
    )
    latest = await lookup.read_run_channel_latest(run_id=_RUN, channel_name="snr")
    assert latest is not None
    assert latest.is_simulated is True
    assert latest.units == "dB"


@pytest.mark.unit
async def test_read_window_returns_zero_count_when_empty() -> None:
    """An empty window is a real signal (the stall candidate), not None."""
    lookup = InMemoryRunChannelLookup()
    signal = await lookup.read_run_channel_window(
        run_id=_RUN, channel_name="projection_index", since=_at(0)
    )
    assert signal.count_since == 0
    assert signal.first_recorded_at is None
    assert signal.latest_recorded_at is None
    assert signal.is_simulated_window is False


@pytest.mark.unit
async def test_read_window_counts_only_arrivals_after_since_floor() -> None:
    """The since floor is exclusive and keys on recorded_at."""
    lookup = InMemoryRunChannelLookup()
    for s in (10, 20, 30, 40):
        lookup.register(
            run_id=_RUN, channel_name="projection_index", value=float(s), recorded_at=_at(s)
        )
    signal = await lookup.read_run_channel_window(
        run_id=_RUN, channel_name="projection_index", since=_at(20)
    )
    assert signal.count_since == 2  # 30 and 40 only; 20 is excluded (strict >)
    assert signal.first_recorded_at == _at(30)
    assert signal.latest_recorded_at == _at(40)


@pytest.mark.unit
async def test_read_window_or_folds_is_simulated_over_window() -> None:
    """Any simulated arrival in the window flips the OR-fold True."""
    lookup = InMemoryRunChannelLookup()
    lookup.register(run_id=_RUN, channel_name="snr", value=1.0, recorded_at=_at(10))
    lookup.register(
        run_id=_RUN, channel_name="snr", value=2.0, recorded_at=_at(20), is_simulated=True
    )
    signal = await lookup.read_run_channel_window(run_id=_RUN, channel_name="snr", since=_at(0))
    assert signal.count_since == 2
    assert signal.is_simulated_window is True

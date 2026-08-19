"""Clock port: testable abstraction over wall-clock and monotonic time."""

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Returns the current time. Implementations may be system-backed or fake."""

    def now(self) -> datetime: ...


class SystemClock:
    """Production adapter: wraps `datetime.now(tz=UTC)`."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)


class FakeClock:
    """Test adapter: returns a controllable time.

    Default semantic is "frozen at construction time" — `now()` returns
    the same `datetime` until `set()` or `advance()` mutates it. Use
    `advance(delta)` to move time forward by a `timedelta` (the common
    case for stale-lock recovery and TTL tests); use `set(at)` to jump
    to an absolute moment.
    """

    def __init__(self, at: datetime) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at

    def set(self, at: datetime) -> None:
        self._at = at

    def advance(self, delta: timedelta) -> None:
        self._at += delta


class MonotonicClock(Protocol):
    """Returns monotonically increasing seconds, for measuring durations.

    Distinct from `Clock`: `Clock.now()` is wall-clock `datetime` (domain
    time, event `occurred_at`, budget windows), which can jump backward
    under an NTP correction, so a duration measured across such a jump is
    wrong or negative. Elapsed GPU time (the serving meter in
    `cora.infrastructure.observability.gpu_accounting`) must read from a
    monotonic source, so it lives on its own port rather than reusing
    `Clock`.
    """

    def now(self) -> float: ...


class SystemMonotonicClock:
    """Production adapter: wraps `time.monotonic()`."""

    def now(self) -> float:
        return time.monotonic()


class FakeMonotonicClock:
    """Test adapter: monotonic seconds that advance only when told.

    Starts at `start` (default 0.0) and moves only via `advance()` or
    `set()`, so a test can place a serving call's open and close at exact
    instants and reproduce an occupancy-share scenario deterministically.
    """

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def set(self, at: float) -> None:
        self._now = at

    def advance(self, seconds: float) -> None:
        self._now += seconds

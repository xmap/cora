"""Run-BC-local read port over a live Run's observation channels.

The read half of the closed-loop observation-signal seam
([[project_observation_signal_port_design]] decision A). Two consumer
rules shape it: Rule Q (quality-within-limits) needs the latest value of
a named channel; Rule R (rate-dropout / stall) needs how many values
arrived in a recent window. Both run inside the RunSupervisor tick.

## BC-local, not promoted to infrastructure/ports

The sole consumer is the composition-root RunSupervisor, which already
imports Run-BC symbols directly; the data-owning sibling
`ObservationStore` is itself BC-internal. So this read counterpart lives
beside the BC, mirroring the `EnclosureObserver` single-root-consumer
precedent. Promote to `infrastructure/ports/` only on a real second
cross-BC consumer (rule-of-three).

## recorded_at is the trust anchor, not sampled_at

`recorded_at` is the Postgres write time (`DEFAULT now()`, CORA-owned);
`sampled_at` is the producer's phenomenonTime and is spoofable /
backfillable. All freshness and arrival-rate math keys on `recorded_at`.
`sampled_at` is surfaced for the human-readable log / Decision line only
and never gates a disposition. This mirrors the run-liveness rule keying
on the un-spoofable `running_since`.

## Simulated data is surfaced, not filtered out

The read returns the latest row regardless of provenance and OR-folds
`is_simulated` over the window. It does NOT hard-filter `is_simulated`:
filtering would (a) hide a real row a misconfigured feeder mislabeled
sim, making a live channel look quiet, and (b) make the sim feeder unable
to exercise the rules end to end. Instead the pure decider treats
`is_simulated` True as disqualifying (defers in act mode, marks the
Decision in advise mode), the read-side mirror of the Operation BC's
ActuationKind "any simulator touch disqualifies" gate.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class RunChannelLatest:
    """The most recent observation on one channel of one Run (Rule Q).

    Returned only when the channel has produced at least one row; a
    `None` return from `read_run_channel_latest` is the cannot-tell case
    (never produced) that the decider defers on.
    """

    channel_name: str
    value: float
    units: str | None
    sampled_at: datetime
    """Producer phenomenonTime. FORENSIC / log only; spoofable, never a
    trust anchor."""
    recorded_at: datetime
    """CORA write time (`DEFAULT now()`). The trusted freshness anchor."""
    is_simulated: bool


@dataclass(frozen=True)
class RunChannelSignal:
    """Windowed arrival summary for one channel of one Run (Rule R).

    Always returned (a zero `count_since` is meaningful: it is the stall
    candidate the decider combines with feed-health + the expected
    interval). `first_recorded_at` / `latest_recorded_at` are None exactly
    when `count_since` is 0.
    """

    channel_name: str
    count_since: int
    """Arrivals with recorded_at strictly greater than the `since` floor."""
    first_recorded_at: datetime | None
    latest_recorded_at: datetime | None
    is_simulated_window: bool
    """OR-fold of is_simulated over the window (any simulated arrival ->
    True). False when the window is empty."""


@dataclass(frozen=True)
class RunFeedHealth:
    """Newest feeder heartbeat for a Run (the dead-feeder seam).

    Carries only the raw recorded_at of the most recent heartbeat across
    all feeder sources (None when no feeder has ever pinged this Run). The
    decider derives liveness: alive iff this is not None AND
    now - latest_heartbeat_recorded_at <= the operator-config ceiling. The
    adapter stays free of the clock and the ceiling.
    """

    latest_heartbeat_recorded_at: datetime | None


class RunChannelLookup(Protocol):
    """Read a live Run's observation channels for the closed-loop rules.

    Two methods because a point read and a windowed aggregate are
    genuinely different queries. Both key freshness on `recorded_at`.
    Production adapter: `PostgresRunChannelLookup` (run/adapters/), backed
    by querying the existing `entries_run_observations` table.
    """

    async def read_run_channel_latest(
        self, *, run_id: UUID, channel_name: str
    ) -> RunChannelLatest | None:
        """Latest value on `channel_name` for `run_id`, or None if the
        channel has never produced a row (cannot-tell -> defer)."""
        ...

    async def read_run_channel_window(
        self, *, run_id: UUID, channel_name: str, since: datetime
    ) -> RunChannelSignal:
        """Arrival summary for `channel_name` since the `recorded_at`
        floor `since`. Always returns a signal; `count_since` may be 0."""
        ...

    async def read_feed_health(self, *, run_id: UUID) -> RunFeedHealth:
        """Newest feeder heartbeat for `run_id` (across sources). The
        decider derives liveness from it + the operator-config ceiling so
        a dead feeder defers the stall rule instead of reading as calm."""
        ...


@dataclass(frozen=True)
class _SeededRow:
    """One seeded observation for the in-memory stub."""

    value: float
    units: str | None
    sampled_at: datetime
    recorded_at: datetime
    is_simulated: bool


class InMemoryRunChannelLookup:
    """Dict-backed, seedable `RunChannelLookup` for unit tests.

    An unseeded instance is the always-quiet default: latest reads return
    None and window reads return a zero-count signal, so the supervisor
    tick is testable with the rules effectively off. Seeded via
    `register(...)` which carries an explicit `recorded_at` (the read
    surfaces recorded_at independently of the write-model `Observation`,
    which does not carry it).
    """

    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, str], list[_SeededRow]] = {}
        self._heartbeats: dict[UUID, list[datetime]] = {}

    def register_heartbeat(self, *, run_id: UUID, recorded_at: datetime) -> None:
        self._heartbeats.setdefault(run_id, []).append(recorded_at)

    def register(
        self,
        *,
        run_id: UUID,
        channel_name: str,
        value: float,
        recorded_at: datetime,
        sampled_at: datetime | None = None,
        units: str | None = None,
        is_simulated: bool = False,
    ) -> None:
        self._rows.setdefault((run_id, channel_name), []).append(
            _SeededRow(
                value=value,
                units=units,
                sampled_at=sampled_at if sampled_at is not None else recorded_at,
                recorded_at=recorded_at,
                is_simulated=is_simulated,
            )
        )

    async def read_run_channel_latest(
        self, *, run_id: UUID, channel_name: str
    ) -> RunChannelLatest | None:
        rows = self._rows.get((run_id, channel_name))
        if not rows:
            return None
        latest = max(rows, key=lambda r: r.recorded_at)
        return RunChannelLatest(
            channel_name=channel_name,
            value=latest.value,
            units=latest.units,
            sampled_at=latest.sampled_at,
            recorded_at=latest.recorded_at,
            is_simulated=latest.is_simulated,
        )

    async def read_run_channel_window(
        self, *, run_id: UUID, channel_name: str, since: datetime
    ) -> RunChannelSignal:
        in_window = [r for r in self._rows.get((run_id, channel_name), []) if r.recorded_at > since]
        if not in_window:
            return RunChannelSignal(
                channel_name=channel_name,
                count_since=0,
                first_recorded_at=None,
                latest_recorded_at=None,
                is_simulated_window=False,
            )
        recorded = [r.recorded_at for r in in_window]
        return RunChannelSignal(
            channel_name=channel_name,
            count_since=len(in_window),
            first_recorded_at=min(recorded),
            latest_recorded_at=max(recorded),
            is_simulated_window=any(r.is_simulated for r in in_window),
        )

    async def read_feed_health(self, *, run_id: UUID) -> RunFeedHealth:
        beats = self._heartbeats.get(run_id)
        return RunFeedHealth(latest_heartbeat_recorded_at=max(beats) if beats else None)


__all__ = [
    "InMemoryRunChannelLookup",
    "RunChannelLatest",
    "RunChannelLookup",
    "RunChannelSignal",
    "RunFeedHealth",
]

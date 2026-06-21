"""Simulation observation feeder: replays a synthetic channel trace.

The sim half of the ingest story
([[project_observation_signal_port_design]] decision B + C). CORA owns the
closed-loop contract and ships ONLY this sim feeder so the rules are
exercisable end to end; each DEPLOYMENT writes its real EPICS /
tomoStream feeder against the SAME write path (the AppendObservations
command + the FeedHeartbeatStore). There is no new ingest port: a feeder
is a runtime over the existing write contract.

Every observation it emits carries `is_simulated=True`, and it writes
under a DISTINCT sim principal (SIM_OBSERVATION_FEEDER_AGENT_ID) so authz
logs and the row `actor_id` can tell sim writes from real (defense in
depth on top of the per-row flag). A real feeder's code path never sets
is_simulated=True, so the only way real data gets marked sim is running it
through this feeder, which the principal split makes visible.

It pings a heartbeat on every drain (even when no data is due), so the
stall rule's dead-feeder seam can distinguish a calm channel from a dead
feeder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from cora.run.aggregates.run import FeedHeartbeat
from cora.run.features.append_observations import AppendObservations, ObservationInput

if TYPE_CHECKING:
    from datetime import datetime

    from cora.infrastructure.ports.clock import Clock
    from cora.infrastructure.ports.id_generator import IdGenerator
    from cora.run.aggregates.run import FeedHeartbeatStore
    from cora.run.features.append_observations.handler import Handler as AppendObservationsHandler

# Distinct sim principal: keeps simulated writes attributable + separable
# from any real feeder principal a deployment configures.
SIM_OBSERVATION_FEEDER_AGENT_ID = UUID("01900000-0000-7000-8000-0000515d0010")


@dataclass(frozen=True)
class TracePoint:
    """One scheduled synthetic observation: emitted once `offset_seconds`
    have elapsed since the feeder's `started_at`."""

    offset_seconds: float
    channel_name: str
    value: float
    units: str | None = None
    sampling_procedure: str = "monitor"


class SimObservationFeeder:
    """Replays a `TracePoint` schedule against the real write path.

    Drive it by advancing the injected `Clock` and calling `drain()`; each
    drain emits the trace points whose offset has elapsed and not yet been
    emitted (is_simulated=True), then writes one heartbeat. Deterministic
    against a FakeClock for tests; a `from_trace` ordering is applied so the
    emitted-prefix bookkeeping holds regardless of input order.
    """

    def __init__(
        self,
        *,
        run_id: UUID,
        started_at: datetime,
        trace: list[TracePoint],
        append_observations: AppendObservationsHandler,
        heartbeat_store: FeedHeartbeatStore,
        clock: Clock,
        id_generator: IdGenerator,
        source_id: str = "sim",
        principal_id: UUID = SIM_OBSERVATION_FEEDER_AGENT_ID,
    ) -> None:
        self._run_id = run_id
        self._started_at = started_at
        self._trace = sorted(trace, key=lambda p: p.offset_seconds)
        self._append_observations = append_observations
        self._heartbeat_store = heartbeat_store
        self._clock = clock
        self._id_generator = id_generator
        self._source_id = source_id
        self._principal_id = principal_id
        self._emitted = 0

    async def drain(self) -> int:
        """Emit every elapsed, not-yet-emitted trace point (is_simulated=True)
        plus one heartbeat. Returns the count of observations emitted."""
        now = self._clock.now()
        elapsed = (now - self._started_at).total_seconds()
        due = [p for p in self._trace[self._emitted :] if p.offset_seconds <= elapsed]
        if due:
            entries = tuple(
                ObservationInput(
                    event_id=self._id_generator.new_id(),
                    channel_name=p.channel_name,
                    value=p.value,
                    sampled_at=now,
                    sampling_procedure=p.sampling_procedure,
                    units=p.units,
                    is_simulated=True,
                )
                for p in due
            )
            await self._append_observations(
                AppendObservations(run_id=self._run_id, entries=entries),
                principal_id=self._principal_id,
                correlation_id=self._id_generator.new_id(),
            )
            self._emitted += len(due)
        await self._heartbeat_store.append(
            [
                FeedHeartbeat(
                    event_id=self._id_generator.new_id(),
                    run_id=self._run_id,
                    source_id=self._source_id,
                    heartbeat_at=now,
                )
            ]
        )
        return len(due)


__all__ = [
    "SIM_OBSERVATION_FEEDER_AGENT_ID",
    "SimObservationFeeder",
    "TracePoint",
]

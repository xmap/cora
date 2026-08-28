"""Application handler for the `get_run_history` query slice.

Reads the Run's OWN event stream directly (not `list_runs`' projection,
not `get_run`'s single fold-and-return): the whole point of this slice is
every exact per-change timestamp CORA already recorded, which a folded
current-state view collapses away. Two changes to the same run inside one
poll tick (e.g. `RunStarted` then `RunHeld` half a second apart) both
survive here, each with its own `occurred_at` / `recorded_at`, which is
exactly what a current-state poll cannot promise.

Deliberately does NOT touch `CapturePathStore` or `ExperimentIdentityStore`
(the two PII/restricted vaults `get_run` resolves into `RunView`): this
slice's output is exactly what the live status-push feature threads to an
external relay off the beamline network, and those two vaults must never
leave it. This is a deliberate difference from `get_run`, not an
oversight.

Query handlers do NOT emit `causation_id` log fields.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from cora.infrastructure.kernel import Kernel
from cora.infrastructure.logging import get_logger
from cora.infrastructure.ports import Deny
from cora.infrastructure.routing import NIL_SENTINEL_ID
from cora.run.aggregates.run import fold, from_stored
from cora.run.errors import UnauthorizedError
from cora.run.features.get_run_history.query import GetRunHistory
from cora.run.ports.run_observation_trail import RunObservationRow, RunObservationTrail

_QUERY_NAME = "GetRunHistory"
_STREAM_TYPE = "Run"
_OBSERVATION_LIMIT = 2000

_log = get_logger(__name__)


@dataclass(frozen=True)
class RunHistoryEvent:
    """One event off the Run's own stream, with its own exact timestamps."""

    event_id: UUID
    event_type: str
    version: int
    occurred_at: datetime
    recorded_at: datetime
    payload: dict[str, Any]


@dataclass(frozen=True)
class RunHistoryView:
    """The full read-side composition for `get_run_history`."""

    run_id: UUID
    name: str
    status: str
    events: list[RunHistoryEvent]
    observations: list[RunObservationRow]
    observations_truncated: bool


class Handler(Protocol):
    """Callable interface every get_run_history handler implements."""

    async def __call__(
        self,
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None: ...


def bind(deps: Kernel, *, observation_trail: RunObservationTrail) -> Handler:
    """Build a get_run_history handler closed over the shared deps."""

    async def handler(
        query: GetRunHistory,
        *,
        principal_id: UUID,
        correlation_id: UUID,
        surface_id: UUID = NIL_SENTINEL_ID,
    ) -> RunHistoryView | None:
        _log.info(
            "get_run_history.start",
            query_name=_QUERY_NAME,
            run_id=str(query.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
        )

        decision = await deps.authz.authorize(
            principal_id=principal_id,
            command_name=_QUERY_NAME,
            conduit_id=NIL_SENTINEL_ID,
            surface_id=surface_id,
        )
        if isinstance(decision, Deny):
            _log.info(
                "get_run_history.denied",
                query_name=_QUERY_NAME,
                run_id=str(query.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                reason=decision.reason,
            )
            raise UnauthorizedError(decision.reason)

        (stored, _version), observations = await asyncio.gather(
            deps.event_store.load(_STREAM_TYPE, query.run_id),
            observation_trail.read_run_observations(
                run_id=query.run_id, limit=_OBSERVATION_LIMIT + 1
            ),
        )
        if not stored:
            _log.info(
                "get_run_history.success",
                query_name=_QUERY_NAME,
                run_id=str(query.run_id),
                principal_id=str(principal_id),
                correlation_id=str(correlation_id),
                found=False,
            )
            return None

        run = fold([from_stored(s) for s in stored])
        assert run is not None  # stored is non-empty, so fold cannot return None

        events = [
            RunHistoryEvent(
                event_id=s.event_id,
                event_type=s.event_type,
                version=s.version,
                occurred_at=s.occurred_at,
                recorded_at=s.recorded_at,
                payload=s.payload,
            )
            for s in stored
        ]
        observations_truncated = len(observations) > _OBSERVATION_LIMIT
        observations = observations[:_OBSERVATION_LIMIT]

        _log.info(
            "get_run_history.success",
            query_name=_QUERY_NAME,
            run_id=str(query.run_id),
            principal_id=str(principal_id),
            correlation_id=str(correlation_id),
            found=True,
            event_count=len(events),
            observation_count=len(observations),
        )
        return RunHistoryView(
            run_id=run.id,
            name=run.name.value,
            status=run.status.value,
            events=events,
            observations=observations,
            observations_truncated=observations_truncated,
        )

    return handler


__all__ = [
    "Handler",
    "RunHistoryEvent",
    "RunHistoryView",
    "bind",
]

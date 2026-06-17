"""Enclosure BC monitor-trigger runtime: drive permit observations from an observer.

Background loop that drains an `EnclosureObserver` (the substrate adapter
is injected; at 2-BM it is the ControlPort-backed permit observer bridged
at the composition root) and records each observation as an
`EnclosurePermitObserved` transition on the matching Enclosure stream.

## Authz: raw decide + append, not the handler

The `observe_enclosure_status` handler authorizes the request principal,
and `SYSTEM_PRINCIPAL_ID` is NOT a wildcard, so a system-driven monitor
calling the handler would be denied. Per the seeder precedent (system
bootstrap writes bypass the operator authorize gate), the loop runs the
same load -> fold -> decide -> append the handler runs, minus authz: a
trusted in-process monitor is not an operator command, and the decider's
Monitor-trigger guard + status-change-only contract are the real safety
gates (the handler docstring notes the request principal is incidental
for monitor-driven facts).

## Resolution + scope

The loop is handed the `{enclosure_name: enclosure_id}` map the seeder
returns, so it resolves observation codes to ids without depending on
projection catch-up timing. The observer scope is the configured names.

## Retry + resilience

`observe()` ends when every PV stream has terminated; the loop waits
`reconnect_delay_seconds` then re-subscribes. A single bad observation is
logged and skipped (the subscription survives). Cancellation (lifespan
shutdown) propagates out of the loop.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from cora.enclosure.aggregates._value_types import EnclosureId
from cora.enclosure.aggregates.enclosure import (
    EnclosureEvent,
    EnclosurePermitStatus,
    MonitorRef,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.enclosure.features.observe_enclosure_status import ObserveEnclosureStatus
from cora.enclosure.features.observe_enclosure_status.decider import decide
from cora.enclosure.ports.enclosure_observer import EnclosureObserverScope
from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.identity import MonitorSourceId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cora.enclosure.ports.enclosure_observer import (
        EnclosureObservation,
        EnclosureObserver,
    )
    from cora.infrastructure.kernel import Kernel

_STREAM_TYPE = "Enclosure"
_COMMAND_NAME = "ObserveEnclosureStatus"
_RECONNECT_DELAY_SECONDS = 5.0

# Stable monitor-source id for the enclosure permit monitor; stamped onto
# EnclosurePermitObserved.triggered_by as the in-process adapter attribution.
ENCLOSURE_PERMIT_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-0000656e6301"))

_log = get_logger(__name__)


async def record_observation(
    kernel: Kernel,
    observation: EnclosureObservation,
    name_to_id: Mapping[str, UUID],
) -> None:
    """Record one observation as an EnclosurePermitObserved (raw, authz-bypassed).

    No-op when the code is unmapped, the status is unparseable, or the
    decider returns `[]` (identical-status, status-change-only).
    """
    enclosure_id = name_to_id.get(observation.enclosure_code)
    if enclosure_id is None:
        _log.warning("enclosure_monitor.unknown_code", enclosure_code=observation.enclosure_code)
        return
    try:
        new_status = EnclosurePermitStatus(observation.observed_status)
    except ValueError:
        _log.warning("enclosure_monitor.bad_status", observed_status=observation.observed_status)
        return

    command = ObserveEnclosureStatus(
        enclosure_id=EnclosureId(enclosure_id),
        new_status=new_status,
        reason=f"PSS permit observation via {observation.source_id}",
        monitor_source_id=ENCLOSURE_PERMIT_MONITOR_SOURCE_ID,
        monitor_ref=MonitorRef(
            source_kind=observation.source_kind, source_id=observation.source_id
        ),
        trigger="Monitor",
    )

    stored, version = await kernel.event_store.load(
        stream_type=_STREAM_TYPE, stream_id=enclosure_id
    )
    history: list[EnclosureEvent] = [from_stored(s) for s in stored]
    state = fold(history)
    domain_events = decide(
        state=state,
        command=command,
        now=kernel.clock.now(),
        triggered_by=ENCLOSURE_PERMIT_MONITOR_SOURCE_ID,
    )
    if not domain_events:
        return
    new_events = [
        to_new_event(
            event_type=event_type_name(event),
            payload=to_payload(event),
            occurred_at=event.occurred_at,
            event_id=kernel.id_generator.new_id(),
            command_name=_COMMAND_NAME,
            correlation_id=kernel.id_generator.new_id(),
            causation_id=None,
            principal_id=SYSTEM_PRINCIPAL_ID,
        )
        for event in domain_events
    ]
    await kernel.event_store.append(
        stream_type=_STREAM_TYPE,
        stream_id=enclosure_id,
        expected_version=version,
        events=new_events,
    )


async def run_enclosure_permit_monitor(
    *,
    observer: EnclosureObserver,
    kernel: Kernel,
    name_to_id: Mapping[str, UUID],
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> None:
    """Drain the observer, recording each observation; re-subscribe on stream end."""
    if not name_to_id:
        return
    scope = EnclosureObserverScope(enclosure_codes=frozenset(name_to_id))
    while True:
        try:
            async for observation in observer.observe(scope):
                try:
                    await record_observation(kernel, observation, name_to_id)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _log.exception(
                        "enclosure_monitor.record_failed",
                        enclosure_code=observation.enclosure_code,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("enclosure_monitor.iteration_failed")
        await asyncio.sleep(reconnect_delay_seconds)


@contextlib.asynccontextmanager
async def enclosure_permit_monitor_lifespan(
    *,
    observer: EnclosureObserver,
    kernel: Kernel,
    name_to_id: Mapping[str, UUID],
) -> AsyncGenerator[None]:
    """Run the permit monitor as a background task for the app's lifetime.

    No-op when `name_to_id` is empty (no enclosures configured): yields
    immediately without starting a task. Mirrors `projection_worker_lifespan`.
    """
    if not name_to_id:
        yield
        return
    task = asyncio.create_task(
        run_enclosure_permit_monitor(observer=observer, kernel=kernel, name_to_id=name_to_id),
        name="enclosure-permit-monitor",
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


__all__ = [
    "ENCLOSURE_PERMIT_MONITOR_SOURCE_ID",
    "enclosure_permit_monitor_lifespan",
    "record_observation",
    "run_enclosure_permit_monitor",
]

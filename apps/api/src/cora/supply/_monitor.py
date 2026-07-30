"""Supply BC monitor-trigger runtime: drive status observations from an observer.

Background loop that drains a `SupplyObserver` (the substrate adapter is
injected; at 2-BM it is the ControlPort-backed BLEPS observer bridged at
the composition root) and records each observation as a status transition
on the matching Supply stream.

Shaped after `cora.enclosure._monitor`, the in-codebase precedent, and
the three notes below are inherited from it verbatim in intent.

## Authz: raw decide + append, not the handler

The `observe_supply_status` handler authorizes the request principal, and
`SYSTEM_PRINCIPAL_ID` is NOT a wildcard, so a system-driven monitor
calling the handler would be denied. Per the seeder precedent (system
bootstrap writes bypass the operator authorize gate), the loop runs the
same load -> fold -> decide -> append the handler runs, minus authz: a
trusted in-process monitor is not an operator command, and the decider's
Monitor-forbidden-target guard plus its status-change-only contract are
the real safety gates.

## Resolution + scope

The loop is handed a `{supply_code: supply_id}` map, so it resolves
observation codes to ids without depending on projection catch-up
timing. The Supply address is a four-tuple
(`facility_code`, `containing_asset_id`, `kind`, `name`) and assembling
it is not an adapter's job; adapters name the resource by code alone.
The observer scope is the configured codes.

## occurred_at comes from the trusted clock, not the observation

`SupplyObservation.observed_at` is carried for diagnostics but is NOT
used as the event's `occurred_at`. A substrate-supplied timestamp could
backdate an event behind ones already appended to the stream, so append
ordering stays on `kernel.clock`. This matches what the Enclosure
runtime actually does; note both observer ports' docstrings argue for
substrate time, so the divergence is deliberate here and recorded as a
watch item in [[project_bleps_ingest_design]].

## Retry + resilience

`observe()` ends when every subscription has terminated; the loop waits
`reconnect_delay_seconds` then re-subscribes. A single bad observation is
logged and skipped so the subscription survives. Cancellation (lifespan
shutdown) propagates out of the loop.

Reconnect is also why the decider's status-change-only rule matters
here rather than being a nicety: a latched substrate republishes every
still-true fault on every re-subscribe, and under the strict contract
this loop would log an exception per channel per reconnect.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING
from uuid import UUID

from cora.infrastructure.event_envelope import to_new_event
from cora.infrastructure.logging import get_logger
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.identity import MonitorSourceId
from cora.supply.aggregates.supply import (
    MonitorRef,
    SupplyEvent,
    SupplyStatus,
    event_type_name,
    fold,
    from_stored,
    to_payload,
)
from cora.supply.features.observe_supply_status import ObserveSupplyStatus
from cora.supply.features.observe_supply_status.decider import decide
from cora.supply.ports.supply_observer import SupplyObserverScope

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cora.infrastructure.kernel import Kernel
    from cora.supply.ports.supply_observer import SupplyObservation, SupplyObserver

_STREAM_TYPE = "Supply"
_COMMAND_NAME = "ObserveSupplyStatus"
_RECONNECT_DELAY_SECONDS = 5.0

# Stable monitor-source id for the supply status monitor; stamped onto
# each transition event's triggered_by as the in-process adapter
# attribution. Distinct from the per-observation monitor_ref, which names
# the specific sensor.
SUPPLY_STATUS_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-000073757001"))

_log = get_logger(__name__)


async def record_observation(
    kernel: Kernel,
    observation: SupplyObservation,
    code_to_id: Mapping[str, UUID],
) -> None:
    """Record one observation as a Supply transition (raw, authz-bypassed).

    No-op when the code is unmapped, the status is unparseable, or the
    decider returns `[]` (unchanged status, status-change-only).
    """
    supply_id = code_to_id.get(observation.supply_code)
    if supply_id is None:
        _log.warning("supply_monitor.unknown_code", supply_code=observation.supply_code)
        return
    try:
        new_status = SupplyStatus(observation.observed_status)
    except ValueError:
        _log.warning("supply_monitor.bad_status", observed_status=observation.observed_status)
        return

    command = ObserveSupplyStatus(
        supply_id=supply_id,
        new_status=new_status,
        monitor_ref=MonitorRef(
            source_kind=observation.source_kind, source_id=observation.source_id
        ),
        monitor_source_id=SUPPLY_STATUS_MONITOR_SOURCE_ID,
        reason=observation.reason,
    )

    stored, version = await kernel.event_store.load(stream_type=_STREAM_TYPE, stream_id=supply_id)
    history: list[SupplyEvent] = [from_stored(s) for s in stored]
    state = fold(history)
    domain_events = decide(
        state=state,
        command=command,
        now=kernel.clock.now(),
        triggered_by=SUPPLY_STATUS_MONITOR_SOURCE_ID,
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
        stream_id=supply_id,
        expected_version=version,
        events=new_events,
    )


async def run_supply_status_monitor(
    *,
    observer: SupplyObserver,
    kernel: Kernel,
    code_to_id: Mapping[str, UUID],
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> None:
    """Drain the observer, recording each observation; re-subscribe on stream end."""
    if not code_to_id:
        return
    scope = SupplyObserverScope(supply_codes=frozenset(code_to_id))
    while True:
        try:
            async for observation in observer.observe(scope):
                try:
                    await record_observation(kernel, observation, code_to_id)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _log.exception(
                        "supply_monitor.record_failed",
                        supply_code=observation.supply_code,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("supply_monitor.iteration_failed")
        await asyncio.sleep(reconnect_delay_seconds)


@contextlib.asynccontextmanager
async def supply_status_monitor_lifespan(
    *,
    observer: SupplyObserver,
    kernel: Kernel,
    code_to_id: Mapping[str, UUID],
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> AsyncGenerator[None]:
    """Run the monitor for the lifetime of the context, cancelling on exit."""
    task = asyncio.create_task(
        run_supply_status_monitor(
            observer=observer,
            kernel=kernel,
            code_to_id=code_to_id,
            reconnect_delay_seconds=reconnect_delay_seconds,
        )
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


__all__ = [
    "SUPPLY_STATUS_MONITOR_SOURCE_ID",
    "record_observation",
    "run_supply_status_monitor",
    "supply_status_monitor_lifespan",
]

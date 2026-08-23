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

## Where "the signals are clear" becomes a transition

Observers report levels and hold no memory of where a Supply has been
(see `cora.api._bleps_supply_observer`). That memory lives in the
aggregate, and this is the only place both the observation and the
aggregate are in hand, so the translation happens here: a `Recovering`
observation is recorded only when the Supply is actually `Unavailable`,
and a `Degraded` observation is dropped when the Supply is already
`Unavailable` (a warning cannot un-downgrade a harder trip); both are
otherwise recorded as-is. Without the first gate, a healthy beamline's
first readings would each be a rejected transition; without the second,
a channel passing back through its own warning band on the way to clear
would log an exception every tick. With an adapter-side memory instead
of these state-aware gates, a re-subscribe or a hand-moved Supply would
silently disagree with the record.
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
    SupplyProbe,
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
    from cora.supply.aggregates.supply import SupplyProbeStore
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
    probe_store: SupplyProbeStore,
) -> None:
    """Record one observation: a Supply-probe row, then, when status-bearing,
    a Supply transition (raw, authz-bypassed).

    No-op entirely when the code is unmapped: the row cannot be
    attributed to a Supply. Otherwise the probe row is written
    unconditionally (except see the degraded-schema case below), in its
    own try/except: a probe-store failure must never suppress the
    transition below it, mirroring `cora.enclosure._monitor`.

    `kernel.schema_posture == "degraded"` skips the probe write entirely:
    a degraded boot runs a read-only event store, so a probe row
    asserting reach during that window would claim coverage over a
    process that cannot actually record what it observed. A GAP in the
    trail is the correct signal there, not a bug.

    `observation.observed_status is None` means this observation is
    probe-only and makes no status claim, so no transition is attempted
    past the probe write. Otherwise, an unparseable status, or the
    decider returning `[]` (unchanged status, status-change-only), are
    no-ops on the transition path only; the probe row still stands.
    """
    supply_id = code_to_id.get(observation.supply_code)
    if supply_id is None:
        _log.warning("supply_monitor.unknown_code", supply_code=observation.supply_code)
        return

    if kernel.schema_posture == "degraded":
        _log.warning(
            "supply_monitor.probe_skipped_degraded_schema",
            supply_code=observation.supply_code,
        )
    else:
        try:
            await probe_store.append(
                [
                    SupplyProbe(
                        event_id=kernel.id_generator.new_id(),
                        supply_id=supply_id,
                        source_kind=observation.source_kind,
                        source_id=observation.source_id,
                        reach_tier=observation.reach_tier,
                        status_claimed=observation.observed_status is not None,
                    )
                ]
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception(
                "supply_monitor.probe_write_failed",
                supply_code=observation.supply_code,
            )

    if observation.observed_status is None:
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

    # A monitor's `Recovering` means "the signals read clear", which is
    # only a fact worth recording about a resource that was down. The
    # observer reports levels and holds no memory, so this is where
    # "clear" becomes either a transition or nothing, read against the
    # aggregate's real status rather than an adapter's recollection of
    # it. Skipping early also keeps the decider from rejecting the
    # common case: on a healthy beamline every initial reading is clear.
    if (
        new_status is SupplyStatus.RECOVERING
        and state is not None
        and state.status is not SupplyStatus.UNAVAILABLE
    ):
        return

    # A warning observed while the Supply is already Unavailable from a
    # harder trip is not "un-downgradable" by a monitor: the decider's
    # `_DEGRADABLE_SOURCES` excludes UNAVAILABLE, by the same latched-
    # alarm precedent as the Recovering skip above (only an operator's
    # `mark_supply_recovering` / `restore_supply` walks a resource back
    # once it has been fully down). Skipping here, rather than letting
    # the decider raise `SupplyCannotDegradeError`, keeps a channel
    # passing back through its own warning band on the way to clear from
    # logging an exception on every tick.
    if (
        new_status is SupplyStatus.DEGRADED
        and state is not None
        and state.status is SupplyStatus.UNAVAILABLE
    ):
        return

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
    probe_store: SupplyProbeStore,
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> None:
    """Drain the observer, recording each observation; re-subscribe on stream end."""
    if not code_to_id:
        return
    scope = SupplyObserverScope(supply_codes=frozenset(code_to_id))
    while True:
        try:
            # No `aclosing`: the port promises only `AsyncIterator`, which
            # has no `aclose`, and stubs are free to return a plain
            # iterator. Generator finalization is therefore left to the
            # event loop, bounded by process shutdown, same as the
            # enclosure precedent.
            async for observation in observer.observe(scope):
                try:
                    await record_observation(kernel, observation, code_to_id, probe_store)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    # A dropped observation is not lost: observers report
                    # levels, so the next reading re-asserts the same
                    # verdict. That is why the adapter holds no edge state.
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
    probe_store: SupplyProbeStore,
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
) -> AsyncGenerator[None]:
    """Run the monitor for the lifetime of the context, cancelling on exit."""
    if not code_to_id:
        # No configured supplies: spawn nothing rather than a task that
        # exists only to return, on every generic boot.
        yield
        return
    task = asyncio.create_task(
        run_supply_status_monitor(
            observer=observer,
            kernel=kernel,
            code_to_id=code_to_id,
            probe_store=probe_store,
            reconnect_delay_seconds=reconnect_delay_seconds,
        ),
        name="supply-status-monitor",
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

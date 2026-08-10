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

## Startup race

Between process start and the monitor's first settled read, `permit_status`
still holds whatever a prior process instance last wrote, so a `start_run` /
`start_procedure` preflight landing in that window can pass on a stale
`Permitted` the current process has not confirmed. `enclosure_permit_monitor_lifespan`
narrows most of that window, in two steps, before yielding to the rest of
boot:

1. It waits, up to a bounded timeout, for every configured enclosure to
   produce one settled observation (a real reading or the observer's own
   `Unknown` on a dead PV). A PV that never answers does not block boot past
   the timeout; the loop keeps retrying in the background and that one
   enclosure's stale reading stands, gated the same as any other stale
   reading.
2. It then drains the enclosure projection once, because step 1 only proves
   an `EnclosurePermitObserved` event was appended (or an append attempt was
   swallowed on failure); `permit_status` is a denormalized read-model
   column the `ProjectionWorker` catches up to on its own poll cadence, and
   the preflight reads that column, never the event stream directly. Like
   step 1, this is bounded: a slow catch-up is logged and boot proceeds
   rather than blocking or failing.

Neither step closes the window to zero: CORA can only observe that a
settlement happened, never that no more are pending, and a PV that never
answers leaves that one enclosure's preflight reading exactly as stale as
before this fix.

## Permit probe trail

Every observation the observer surfaces, whether or not it carries a
status claim, is also recorded as a `PermitProbe` row: an append-only
fact about whether CORA reached the permit substrate, kept separate from
`EnclosurePermitObserved`'s record of what the interlock said. See
[[project_enclosure_permit_probe_design]]. The probe write happens in
its own try/except, before the transition attempt, so a bookkeeping
failure there can never suppress a real permit transition (the reverse
of "Startup race" above: this failure mode makes the record LESS
truthful, not the boot LESS available, so it degrades by logging and
continuing rather than by warning and proceeding).

`observation.observed_status is None` means the observation is
probe-only (a periodic re-affirmation read that intentionally makes no
status claim): the probe row is still written, but no permit transition
is attempted and no startup-readiness code is settled by it (see
`run_enclosure_permit_monitor`), because it proves nothing about
whether the enclosure's actual permit-status has been confirmed.

No probe row is written at all while `kernel.schema_posture ==
"degraded"` (a boot running under `ALLOW_SCHEMA_VERSION_MISMATCH`,
whose event store is read-only): a probe row asserting reach during a
window where CORA cannot actually record what it observed would be
worse than silence. The resulting gap in the trail is the correct
signal, not a bug.
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
    PermitProbe,
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
from cora.infrastructure.projection import ProjectionDrainTimeoutError, drain_projections
from cora.infrastructure.routing import SYSTEM_PRINCIPAL_ID
from cora.shared.identity import MonitorSourceId

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from cora.enclosure.aggregates.enclosure import PermitProbeStore
    from cora.enclosure.ports.enclosure_observer import (
        EnclosureObservation,
        EnclosureObserver,
    )
    from cora.infrastructure.kernel import Kernel
    from cora.infrastructure.projection import ProjectionRegistry

_STREAM_TYPE = "Enclosure"
_COMMAND_NAME = "ObserveEnclosureStatus"
_RECONNECT_DELAY_SECONDS = 5.0
# A few seconds above EpicsCaControlPort's own _DEFAULT_TIMEOUT_S (5.0s):
# a dead PV's per-code settlement (pump reaching Unknown via a bounded
# connect attempt) needs room to finish before this outer bound gives up,
# or every dead-PV boot falls through to the blunter warn-and-proceed path
# instead of the cleaner "every code settled, including Unknown" one.
_STARTUP_TIMEOUT_SECONDS = 8.0
_PROJECTION_DRAIN_DEADLINE_SECONDS = 5.0

# Stable monitor-source id for the enclosure permit monitor; stamped onto
# EnclosurePermitObserved.triggered_by as the in-process adapter attribution.
ENCLOSURE_PERMIT_MONITOR_SOURCE_ID = MonitorSourceId(UUID("01900000-0000-7000-8000-0000656e6301"))

_log = get_logger(__name__)


async def record_observation(
    kernel: Kernel,
    observation: EnclosureObservation,
    name_to_id: Mapping[str, UUID],
    probe_store: PermitProbeStore,
) -> None:
    """Record one observation: a permit-probe row, then, when status-bearing,
    an EnclosurePermitObserved transition (raw, authz-bypassed).

    No-op entirely when the code is unmapped: the row cannot be
    attributed to an enclosure. Otherwise the probe row is written
    unconditionally (except see the degraded-schema case below), in its
    own try/except: a probe-store failure must never suppress the
    transition below it (a bookkeeping table must never take down the
    safety-relevant record it exists to annotate).

    `kernel.schema_posture == "degraded"` skips the probe write entirely
    rather than writing one: a degraded boot runs a read-only event
    store (see `Kernel.schema_posture`), so a probe row asserting reach
    during that window would claim coverage over a process that cannot
    actually record what it observed. A GAP in the trail here is the
    correct signal, not a bug: it is exactly the "CORA was not really
    watching" fact the trail exists to preserve, and writing a row would
    hide it behind a dense, misleading RELAYED/UNREACHED history.

    `observation.observed_status is None` means this observation is
    probe-only and makes no status claim, so no transition is attempted
    past the probe write. Otherwise, an unparseable status, or the
    decider returning `[]` (identical-status, status-change-only), are
    no-ops on the transition path only; the probe row still stands.
    """
    enclosure_id = name_to_id.get(observation.enclosure_code)
    if enclosure_id is None:
        _log.warning("enclosure_monitor.unknown_code", enclosure_code=observation.enclosure_code)
        return

    if kernel.schema_posture == "degraded":
        _log.warning(
            "enclosure_monitor.probe_skipped_degraded_schema",
            enclosure_code=observation.enclosure_code,
        )
    else:
        try:
            await probe_store.append(
                [
                    PermitProbe(
                        event_id=kernel.id_generator.new_id(),
                        enclosure_id=enclosure_id,
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
                "enclosure_monitor.probe_write_failed",
                enclosure_code=observation.enclosure_code,
            )

    if observation.observed_status is None:
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
        # The seam used to stop here and drop this. `occurred_at` on the
        # emitted event still records when CORA learned of the reading;
        # this records when the substrate says it took it, or None when
        # the substrate said nothing, which at 2-BM is every reading.
        observed_at=observation.observed_at,
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
    probe_store: PermitProbeStore,
    reconnect_delay_seconds: float = _RECONNECT_DELAY_SECONDS,
    startup_ready: asyncio.Event | None = None,
) -> None:
    """Drain the observer, recording each observation; re-subscribe on stream end.

    `startup_ready`, when given, is set once every configured enclosure code
    has produced one STATUS-BEARING observation (a real reading, or the
    observer's own `Unknown` on a dead PV; `observation.observed_status is
    not None`). A probe-only observation (a periodic re-affirmation poll,
    `observed_status is None`) never settles a code: it proves reach, not
    that the enclosure's permit status has been confirmed, and settling on
    it would let a poll-only pass mark boot ready while the actual permit
    transition attempt (which only a status-bearing observation can make)
    never happened, serving a stale `permit_status` boot never confirmed.

    Failing that, `startup_ready` is set once a full pass ends (the
    observer's stream terminated or raised) with every code still settled
    from a PRIOR pass, i.e. `pending_codes` is already empty; a pass that
    ends with codes still pending (a total connection failure, or the
    observer producing nothing at all) does NOT settle `startup_ready`
    here, so the caller's own bounded wait (see `enclosure_permit_monitor_lifespan`)
    is what gives up on a deployment that cannot connect at all, rather
    than this loop falsely reporting readiness for a code it never heard
    a status-bearing observation for. `Event.set` on an already-set event
    is a no-op, so the caller only ever sees the earliest settlement.
    """
    if not name_to_id:
        return
    scope = EnclosureObserverScope(enclosure_codes=frozenset(name_to_id))
    pending_codes: set[str] = set(name_to_id) if startup_ready is not None else set()
    while True:
        try:
            async for observation in observer.observe(scope):
                try:
                    await record_observation(kernel, observation, name_to_id, probe_store)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _log.exception(
                        "enclosure_monitor.record_failed",
                        enclosure_code=observation.enclosure_code,
                    )
                if observation.observed_status is not None:
                    pending_codes.discard(observation.enclosure_code)
                    if startup_ready is not None and not pending_codes:
                        startup_ready.set()
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("enclosure_monitor.iteration_failed")
        if startup_ready is not None and not pending_codes:
            startup_ready.set()
        await asyncio.sleep(reconnect_delay_seconds)


@contextlib.asynccontextmanager
async def enclosure_permit_monitor_lifespan(
    *,
    observer: EnclosureObserver,
    kernel: Kernel,
    name_to_id: Mapping[str, UUID],
    probe_store: PermitProbeStore,
    enclosure_projection_registry: ProjectionRegistry | None = None,
    startup_timeout_seconds: float = _STARTUP_TIMEOUT_SECONDS,
) -> AsyncGenerator[None]:
    """Run the permit monitor as a background task for the app's lifetime.

    No-op when `name_to_id` is empty (no enclosures configured): yields
    immediately without starting a task. Mirrors `projection_worker_lifespan`.

    Otherwise, before yielding: waits up to `startup_timeout_seconds` for
    every configured enclosure's first settled observation, then, when
    `enclosure_projection_registry` is given and `kernel.pool` is a real
    pool, drains it once. Both steps exist because neither alone gets a
    preflight landing right after boot to a status this process has
    confirmed (see module docstring, "Startup race"): the wait only proves
    an event was appended (or an append attempt failed and was logged); the
    drain is what catches `permit_status` itself up to that event. A PV
    that never settles does not delay boot past `startup_timeout_seconds`:
    the background task keeps retrying and that enclosure's existing
    reading stands, gated the same as any other stale reading.
    `enclosure_projection_registry` is optional so tests that stub `kernel`
    can omit it and skip the drain entirely.
    """
    if not name_to_id:
        yield
        return
    startup_ready = asyncio.Event()
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=kernel,
            name_to_id=name_to_id,
            probe_store=probe_store,
            startup_ready=startup_ready,
        ),
        name="enclosure-permit-monitor",
    )
    try:
        try:
            await asyncio.wait_for(startup_ready.wait(), timeout=startup_timeout_seconds)
        except TimeoutError:
            _log.warning(
                "enclosure_monitor.startup_timeout",
                startup_timeout_seconds=startup_timeout_seconds,
                enclosure_codes=sorted(name_to_id),
            )
        if enclosure_projection_registry is not None and kernel.pool is not None:
            try:
                await drain_projections(
                    kernel.pool,
                    enclosure_projection_registry,
                    deadline_seconds=_PROJECTION_DRAIN_DEADLINE_SECONDS,
                )
            except ProjectionDrainTimeoutError:
                # Same posture as the startup_timeout_seconds branch above:
                # a slow catch-up degrades permit_status freshness, it must
                # never abort boot. Letting this propagate would turn a
                # read-honesty fix into an availability regression, which is
                # a worse trade than the staleness this fix exists to narrow.
                _log.warning(
                    "enclosure_monitor.projection_drain_timeout",
                    deadline_seconds=_PROJECTION_DRAIN_DEADLINE_SECONDS,
                    enclosure_codes=sorted(name_to_id),
                )
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

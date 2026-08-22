"""DurableCopyRegistrar's periodic sweep: lifespan wiring.

Mirrors `cora.api._capture_scan_ingestor.capture_scan_ingestor_lifespan`
phase for phase: kill-switch early return that still yields, a startup
grant probe, a pool-conditional candidate lookup, and a `_sweep_loop`
that logs and carries on rather than letting one bad tick take the
whole task down.

## The driver instance is long-lived, on purpose

`DurableDistributionDriver` carries a keyset cursor as instance state
(`self._cursor`). Constructing a fresh driver per tick would reset that
cursor to `None` on every call, reproducing exactly the starvation the
cursor was built to prevent (see `_durable_distribution_driver`'s own
module docstring): a population of permanently-stuck candidates would
consume the whole attempt budget every tick and the sweep would never
reach anything past them. The driver here is built ONCE, outside
`_sweep_loop`, and the loop calls `.tick()` on the same instance
forever.

## Why the probe and the checksum computer are both SSH-only here

`SshLocateProbe` is the only `LocateProbe` this codebase ships (no
local counterpart exists, matching the fact that at 2-BM the durable
copy is never on CORA's own host); the boot guard
(`_enforce_run_witness_recording_gate`) refuses to enable the sweep
without `scan_probe_remote_host` set, so by the time this module runs
the assertions below hold. The checksum computer is built through the
SAME `active_scan_transport` conditional `cora.data.wire
._build_scan_ingest_pair` uses for `ingest_scan`, sharing one
`SshProbeConfig` with the probe: both must reach the SAME host that
holds the bytes, or the digest silently runs against a host that never
had them.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from cora.agent.seed_durable_copy_registrar import DURABLE_COPY_REGISTRAR_AGENT_ID
from cora.api._durable_copy_registrar import DigestingDurableCopyRegistrar
from cora.api._durable_distribution_driver import DurableDistributionDriver
from cora.api._durable_distribution_sweep import (
    DurableDistributionCandidateLookup,
    NeverDurableDistributionCandidateLookup,
    PostgresDurableDistributionCandidateLookup,
)
from cora.api._flag_watcher import probe_read_grant
from cora.data.adapters._ssh_probe import SshProbeConfig
from cora.data.adapters.capture_path_locator import active_scan_transport
from cora.data.adapters.ssh_locate_probe import SshLocateProbe
from cora.data.adapters.ssh_posix_checksum_computer import SshPosixChecksumComputer
from cora.infrastructure.capture_scan_ingestor_binding import (
    CaptureScanIngestorDurableLocationLookup,
    durable_roots,
    durable_supply_ids,
)
from cora.infrastructure.logging import get_logger
from cora.run.aggregates.run import InMemoryCapturePathStore, PostgresCapturePathStore

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from cora.infrastructure.kernel import Kernel

_log = get_logger(__name__)

_READ_COMMAND = "RegisterDistribution"
_LOG_PREFIX = "durable_distribution"


async def _sweep_loop(driver: DurableDistributionDriver, *, interval_seconds: float) -> None:
    """Periodic sweep. A failed tick is logged (inside `tick()` itself,
    which never raises); cancellation propagates."""
    while True:
        try:
            await driver.tick()
        except asyncio.CancelledError:
            raise
        except Exception:
            _log.exception("durable_distribution.tick_failed")
        await asyncio.sleep(interval_seconds)


@contextlib.asynccontextmanager
async def durable_distribution_lifespan(
    deps: Kernel, *, interval_seconds: float | None = None
) -> AsyncGenerator[None]:
    """Spawn the durable-distribution sweep for the duration of the
    context. No-op unless `settings.durable_distribution_sweep_enabled`
    is True (default off, so a deployment opts in explicitly). When
    enabled, probes the `RegisterDistribution` grant once at startup (or
    refuses boot in strict mode) so a missing grant is surfaced
    immediately rather than only at the first denied tick, mirroring
    every sibling watcher/writer runtime's `probe_read_grant` startup
    check.

    `interval_seconds` overrides `settings.durable_distribution_sweep_tick_seconds`;
    tests use it to avoid a 30-second real wait, mirroring
    `capture_scan_ingestor_lifespan`'s identical parameter.
    """
    if not deps.settings.durable_distribution_sweep_enabled:
        _log.info("durable_distribution.skipped", reason="disabled")
        yield
        return

    await probe_read_grant(
        deps,
        agent_id=DURABLE_COPY_REGISTRAR_AGENT_ID,
        read_command=_READ_COMMAND,
        log_prefix=_LOG_PREFIX,
        strict=deps.settings.watcher_authz_strict,
    )

    bindings = deps.settings.capture_scan_ingestor_bindings
    candidate_lookup: DurableDistributionCandidateLookup = (
        PostgresDurableDistributionCandidateLookup(
            deps.pool,
            durable_roots=durable_roots(bindings),
            durable_supply_ids=durable_supply_ids(bindings),
        )
        if deps.pool is not None
        else NeverDurableDistributionCandidateLookup()
    )

    # Same transport the locator minting uses (see module docstring):
    # the boot guard guarantees scan_probe_remote_host is set whenever
    # this lifespan runs for real.
    host, roots = active_scan_transport(deps)
    remote_host = deps.settings.scan_probe_remote_host
    assert remote_host is not None, (
        "durable_distribution_sweep_enabled=True; "
        "_enforce_run_witness_recording_gate guarantees scan_probe_remote_host is set"
    )
    remote_python = deps.settings.scan_probe_remote_python
    assert remote_python is not None, (
        "scan_probe_remote_host is set; Settings validation guarantees "
        "scan_probe_remote_python is too"
    )
    config = SshProbeConfig(
        host=host,
        remote_python=remote_python,
        allowed_roots=roots,
        connect_timeout_seconds=deps.settings.scan_probe_ssh_connect_timeout_seconds,
        command_timeout_seconds=deps.settings.scan_probe_ssh_command_timeout_seconds,
        max_walk_seconds=deps.settings.posix_checksum_max_walk_seconds,
    )

    registrar = DigestingDurableCopyRegistrar(
        event_store=deps.event_store,
        authz=deps.authz,
        supply_lookup=deps.supply_lookup,
        checksum_computer=SshPosixChecksumComputer(config=config),
        clock=deps.clock,
        id_generator=deps.id_generator,
    )
    capture_paths = (
        PostgresCapturePathStore(deps.pool) if deps.pool is not None else InMemoryCapturePathStore()
    )
    driver = DurableDistributionDriver(
        candidate_lookup=candidate_lookup,
        durable_locations=CaptureScanIngestorDurableLocationLookup(bindings),
        probe=SshLocateProbe(config=config),
        capture_paths=capture_paths,
        registrar=registrar,
        host=host,
        clock=deps.clock,
    )

    default_interval = deps.settings.durable_distribution_sweep_tick_seconds
    interval = interval_seconds if interval_seconds is not None else default_interval
    _log.info("durable_distribution.started", interval_seconds=interval)
    task = asyncio.create_task(
        _sweep_loop(driver, interval_seconds=interval), name="durable-distribution-sweep"
    )
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        _log.info("durable_distribution.stopped")


__all__ = ["durable_distribution_lifespan"]

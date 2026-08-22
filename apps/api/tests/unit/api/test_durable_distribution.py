"""Unit tests for `durable_distribution_lifespan` (cora.api._durable_distribution).

The driver's own tick dispatch logic (`DurableDistributionDriver`) is
covered in `test_durable_distribution_driver.py` against fakes; this
file covers only the lifespan's own phases: the kill-switch no-op, the
enabled path wiring up a real sweep task, and `_sweep_loop`'s
never-raise / cancellation-propagates contract. No pool is configured
here (in-memory `Kernel`), so the candidate lookup always falls back to
`NeverDurableDistributionCandidateLookup` and no real tick ever finds a
candidate; the SQL-backed lookup is an integration-tier concern.
"""

# reportPrivateUsage: two tests drive `_sweep_loop` directly against a
# minimal fake driver, since the lifespan builds its own real driver
# from `deps` and cannot be handed a raising or hanging one.
# pyright: reportPrivateUsage=false

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
import structlog.testing

from cora.api._durable_distribution import _sweep_loop, durable_distribution_lifespan
from cora.api._durable_distribution_driver import DurableDistributionDriver
from cora.infrastructure.capture_scan_ingestor_binding import (
    CaptureScanIngestorBinding,
    CaptureScanIngestorLocation,
)
from cora.infrastructure.deps import make_inmemory_kernel
from cora.infrastructure.ports import AllowAllAuthorize, FakeClock, FixedIdGenerator
from tests.unit._helpers import DEFAULT_NOW

pytestmark = pytest.mark.unit

_ACQUISITION_ROOT = "/local1/2BM"
_DURABLE_ROOT = "/gdata/dm/2BM"


def _durable_bindings() -> dict[str, CaptureScanIngestorBinding]:
    return {
        "2bmb-tomoscan": CaptureScanIngestorBinding(
            producing_asset_id=uuid4(),
            locations={
                _ACQUISITION_ROOT: CaptureScanIngestorLocation(
                    supply_id=uuid4(), access_protocol="POSIX"
                ),
                _DURABLE_ROOT: CaptureScanIngestorLocation(
                    supply_id=uuid4(), access_protocol="NFS", durable=True
                ),
            },
        )
    }


def _deps(**settings_kwargs: Any) -> Any:
    from cora.infrastructure.config import Settings

    settings_kwargs.setdefault("scan_probe_allowed_roots", (_ACQUISITION_ROOT, _DURABLE_ROOT))
    settings_kwargs.setdefault("scan_probe_remote_host", "tomdet")
    settings_kwargs.setdefault("scan_probe_remote_python", "/venv/bin/python3")
    return make_inmemory_kernel(
        settings=Settings(**settings_kwargs),  # type: ignore[call-arg]
        clock=FakeClock(DEFAULT_NOW),
        id_generator=FixedIdGenerator([uuid4() for _ in range(10)]),
        authz=AllowAllAuthorize(),
    )


async def test_lifespan_disabled_is_a_no_op() -> None:
    deps = _deps(durable_distribution_sweep_enabled=False)

    with structlog.testing.capture_logs() as logs:
        async with durable_distribution_lifespan(deps):
            pass

    events = [entry.get("event") for entry in logs]
    assert "durable_distribution.skipped" in events
    assert "durable_distribution.started" not in events


async def test_lifespan_enabled_sweeps_until_the_context_exits() -> None:
    """The enabled path end to end: startup grant probe, candidate-lookup
    selection (no pool here, so the Never fallback), spawned sweep task,
    and cancellation on exit. Without this the whole enabled branch of
    the lifespan runs for the first time on the deployment."""
    deps = _deps(
        durable_distribution_sweep_enabled=True,
        capture_path_recording_enabled=True,
        capture_scan_ingestor_bindings=_durable_bindings(),
    )

    with structlog.testing.capture_logs() as logs:
        async with durable_distribution_lifespan(deps, interval_seconds=0.01):
            await asyncio.sleep(0.05)

    events = [entry.get("event") for entry in logs]
    assert "durable_distribution.started" in events
    assert "durable_distribution.stopped" in events


async def test_lifespan_constructs_the_driver_exactly_once_across_many_ticks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation this test exists to catch: a `DurableDistributionDriver`
    built freshly per tick resets its keyset cursor to `None` on every
    call, reproducing the exact starvation the cursor was built to
    prevent. Counts real constructions across several tick intervals;
    it must stay at exactly one regardless of how many ticks ran."""
    construct_count = 0
    original_init = DurableDistributionDriver.__init__

    def _counting_init(self: DurableDistributionDriver, *args: Any, **kwargs: Any) -> None:
        nonlocal construct_count
        construct_count += 1
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(DurableDistributionDriver, "__init__", _counting_init)

    deps = _deps(
        durable_distribution_sweep_enabled=True,
        capture_path_recording_enabled=True,
        capture_scan_ingestor_bindings=_durable_bindings(),
    )

    async with durable_distribution_lifespan(deps, interval_seconds=0.01):
        await asyncio.sleep(0.05)

    assert construct_count == 1


async def test_sweep_loop_survives_a_tick_that_raises() -> None:
    class _RaisingDriver:
        def __init__(self) -> None:
            self.calls = 0

        async def tick(self) -> None:
            self.calls += 1
            raise RuntimeError("boom")

    driver = _RaisingDriver()
    task = asyncio.create_task(_sweep_loop(driver, interval_seconds=0.01))  # type: ignore[arg-type]
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert driver.calls >= 2


async def test_sweep_loop_propagates_cancellation_instead_of_swallowing_it() -> None:
    entered = asyncio.Event()

    class _HangingDriver:
        async def tick(self) -> None:
            entered.set()
            await asyncio.sleep(10)

    task = asyncio.create_task(_sweep_loop(_HangingDriver(), interval_seconds=10))  # type: ignore[arg-type]
    await asyncio.wait_for(entered.wait(), timeout=1)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)

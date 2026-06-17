"""Tests for the Enclosure permit monitor runtime (`_monitor.py`).

`record_observation` is pinned deterministically against a real event
store (maps an observation to an EnclosurePermitObserved transition,
status-change-only idempotency, unknown-code no-op). The retry loop +
lifespan are covered for the empty-config no-op path and for a
fake-observer drive that records one observation end to end.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import asyncio
import contextlib
import dataclasses
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.enclosure import seed_enclosures
from cora.enclosure._monitor import (
    enclosure_permit_monitor_lifespan,
    record_observation,
    run_enclosure_permit_monitor,
)
from cora.enclosure.adapters import PostgresEnclosureLookup
from cora.enclosure.ports.enclosure_observer import (
    EnclosureObservation,
    EnclosureObserverScope,
)
from cora.infrastructure.config import Settings
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.ports.event_store import StoredEvent
from tests.integration._helpers import build_postgres_deps

_T = datetime(2026, 6, 17, 12, 0, 0, tzinfo=UTC)


def _deps_with(db_pool: asyncpg.Pool, *, permit_pvs: dict[str, str]) -> Kernel:
    deps = build_postgres_deps(db_pool, now=_T, ids=[uuid4() for _ in range(12)])
    return dataclasses.replace(
        deps,
        settings=Settings(app_env="test", enclosure_permit_pvs=permit_pvs),  # type: ignore[call-arg]
        enclosure_lookup=PostgresEnclosureLookup(db_pool),
    )


def _obs(name: str, status: str, *, pv: str = "S02BM-PSS:StaA:SecureM") -> EnclosureObservation:
    return EnclosureObservation(
        enclosure_code=name,
        observed_status=status,
        observed_at=_T,
        source_kind="EpicsPv",
        source_id=pv,
    )


async def _permit_events(deps: Kernel, enclosure_id: UUID) -> list[StoredEvent]:
    events, _ = await deps.event_store.load(stream_type="Enclosure", stream_id=enclosure_id)
    return [e for e in events if e.event_type == "EnclosurePermitObserved"]


@pytest.mark.integration
async def test_record_observation_writes_permit_observed(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-rec-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)

    await record_observation(deps, _obs(name, "Permitted"), name_to_id)

    events = await _permit_events(deps, name_to_id[name])
    assert len(events) == 1
    assert events[0].payload["from_status"] == "Unknown"
    assert events[0].payload["to_status"] == "Permitted"


@pytest.mark.integration
async def test_record_observation_same_status_is_noop(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-idem-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)

    await record_observation(deps, _obs(name, "Permitted"), name_to_id)
    await record_observation(deps, _obs(name, "Permitted"), name_to_id)

    assert len(await _permit_events(deps, name_to_id[name])) == 1


@pytest.mark.integration
async def test_record_observation_unknown_code_is_noop(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-known-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)

    # observation for a code that was never seeded -> skipped, no raise
    await record_observation(deps, _obs("not-a-hutch", "Permitted"), name_to_id)
    assert await _permit_events(deps, name_to_id[name]) == []


@pytest.mark.unit
async def test_run_monitor_empty_map_returns_immediately() -> None:
    await run_enclosure_permit_monitor(
        observer=_FakeObserver([]), kernel=cast("Kernel", None), name_to_id={}
    )


@pytest.mark.unit
async def test_lifespan_empty_map_is_noop() -> None:
    async with enclosure_permit_monitor_lifespan(
        observer=_FakeObserver([]), kernel=cast("Kernel", None), name_to_id={}
    ):
        pass  # yields without starting a task; kernel/observer untouched


@pytest.mark.integration
async def test_loop_records_observation_from_observer(db_pool: asyncpg.Pool) -> None:
    name = f"hutch-loop-{uuid4().hex[:8]}"
    deps = _deps_with(db_pool, permit_pvs={name: "pv"})
    name_to_id = await seed_enclosures(deps)
    enclosure_id = name_to_id[name]

    observer = _FakeObserver([_obs(name, "Permitted")])
    task = asyncio.create_task(
        run_enclosure_permit_monitor(
            observer=observer,
            kernel=deps,
            name_to_id=name_to_id,
            reconnect_delay_seconds=3600.0,  # one pass, then idle (test cancels)
        )
    )
    try:
        for _ in range(200):
            if await _permit_events(deps, enclosure_id):
                break
            await asyncio.sleep(0.01)
        else:  # pragma: no cover - failure path
            raise AssertionError("monitor did not record the observation")
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    events = await _permit_events(deps, enclosure_id)
    assert len(events) == 1
    assert events[0].payload["to_status"] == "Permitted"


class _FakeObserver:
    """Yields a fixed observation sequence once, then ends the stream."""

    def __init__(self, observations: list[EnclosureObservation]) -> None:
        self._observations = observations

    def observe(self, scope: EnclosureObserverScope) -> AsyncGenerator[EnclosureObservation]:
        return self._drain()

    async def _drain(self) -> AsyncGenerator[EnclosureObservation]:
        for observation in self._observations:
            yield observation

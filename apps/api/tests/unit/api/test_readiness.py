"""Unit tests for the /readyz probe helper.

These drive the branches the contract tier structurally cannot reach:
`tests/conftest.py` forces APP_ENV=test process-wide, which builds the
in-memory kernel with `pool=None`, so an app-level test only ever
exercises the `skipped` path. Every fake below stands in for a pool.

The bounded-acquire test is the load-bearing one. `Pool.fetchval(q,
timeout=T)` bounds the query but calls `acquire()` with no timeout, so
a probe written the obvious way hangs forever on a saturated pool. That
test is what fails if someone later "simplifies" the helper.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from cora.api._readiness import derive_actuation, probe_database, readiness_body
from cora.infrastructure.config import Settings


class _Conn:
    def __init__(self, fetchval_error: Exception | None = None) -> None:
        self._fetchval_error = fetchval_error

    async def fetchval(self, query: str) -> int:
        if self._fetchval_error is not None:
            raise self._fetchval_error
        return 1


class _AcquireContext:
    """Mirrors `asyncpg.Pool.acquire`, which returns a context manager.

    The shape matters: the probe does `async with pool.acquire(...)`, so
    a fake that merely returns a connection would not exercise the code
    under test.
    """

    def __init__(self, pool: _FakePool) -> None:
        self._pool = pool

    async def __aenter__(self) -> _Conn:
        if self._pool.acquire_delay_s:
            await asyncio.sleep(self._pool.acquire_delay_s)
        if self._pool.acquire_error is not None:
            raise self._pool.acquire_error
        return _Conn(self._pool.fetchval_error)

    async def __aexit__(self, *exc_info: object) -> None:
        self._pool.released += 1


class _FakePool:
    """Pool stand-in whose acquire behaviour each test dictates."""

    def __init__(
        self,
        *,
        acquire_error: Exception | None = None,
        acquire_delay_s: float = 0.0,
        fetchval_error: Exception | None = None,
    ) -> None:
        self.acquire_error = acquire_error
        self.acquire_delay_s = acquire_delay_s
        self.fetchval_error = fetchval_error
        self.released = 0

    def acquire(self, *, timeout: float | None = None) -> _AcquireContext:
        return _AcquireContext(self)


def _settings() -> Settings:
    return Settings(app_env="test")


@pytest.mark.unit
async def test_probe_database_with_no_pool_reports_skipped() -> None:
    """The in-memory kernel has no pool; that is nothing to report, not a fault."""
    assert await probe_database(None) == "skipped"


@pytest.mark.unit
async def test_probe_database_with_healthy_pool_reports_ok() -> None:
    assert await probe_database(_FakePool()) == "ok"  # type: ignore[arg-type]


@pytest.mark.unit
async def test_probe_database_releases_the_connection() -> None:
    """A probe that leaks a connection per period exhausts the pool it watches."""
    pool = _FakePool()
    await probe_database(pool)  # type: ignore[arg-type]
    assert pool.released == 1


@pytest.mark.unit
async def test_probe_database_releases_the_connection_when_the_query_fails() -> None:
    """The release must survive the failure path, or a flapping DB drains the pool."""
    pool = _FakePool(fetchval_error=asyncpg.PostgresError("boom"))
    await probe_database(pool)  # type: ignore[arg-type]
    assert pool.released == 1


@pytest.mark.unit
async def test_probe_database_bounds_a_hanging_acquire() -> None:
    """The property that matters: a saturated pool must not hang the probe.

    Pins the reason both timeouts exist. `Pool.fetchval(timeout=)` would
    NOT bound this, because it forwards the timeout to the query and
    waits unbounded for a connection.
    """
    pool = _FakePool(acquire_delay_s=30.0)
    async with asyncio.timeout(5.0):  # test-level backstop; the probe must finish first
        assert await probe_database(pool) == "saturated"  # type: ignore[arg-type]


@pytest.mark.unit
async def test_probe_database_with_unreachable_postgres_reports_unreachable() -> None:
    pool = _FakePool(acquire_error=OSError("connection refused"))
    assert await probe_database(pool) == "unreachable"  # type: ignore[arg-type]


@pytest.mark.unit
async def test_probe_database_during_shutdown_reports_closing() -> None:
    """InterfaceError is not a PostgresError, so a narrow catch would miss it."""
    pool = _FakePool(acquire_error=asyncpg.InterfaceError("pool is closing"))
    assert await probe_database(pool) == "closing"  # type: ignore[arg-type]


@pytest.mark.unit
async def test_probe_database_with_failing_query_reports_error() -> None:
    pool = _FakePool(fetchval_error=asyncpg.PostgresError("boom"))
    assert await probe_database(pool) == "error"  # type: ignore[arg-type]


@pytest.mark.unit
async def test_probe_database_never_raises_on_an_unenumerated_failure() -> None:
    """A probe that raises turns an outage into a 500 that reads as a bug."""
    pool = _FakePool(acquire_error=RuntimeError("something nobody predicted"))
    assert await probe_database(pool) == "error"  # type: ignore[arg-type]


@pytest.mark.unit
def test_readiness_body_reports_ready_when_database_ok() -> None:
    body = readiness_body("ok", _settings())
    assert body["status"] == "ready"
    assert body["database"] == "ok"


@pytest.mark.unit
def test_readiness_body_reports_ready_when_database_skipped() -> None:
    """No pool configured is a deployment shape, not an outage."""
    assert readiness_body("skipped", _settings())["status"] == "ready"


@pytest.mark.unit
@pytest.mark.parametrize("database", ["unreachable", "saturated", "closing", "error"])
def test_readiness_body_reports_not_ready_on_any_database_fault(database: str) -> None:
    assert readiness_body(database, _settings())["status"] == "not_ready"  # type: ignore[arg-type]


@pytest.mark.unit
def test_readiness_body_carries_app_env() -> None:
    """A green probe over an in-memory store is worth making visible."""
    assert readiness_body("skipped", _settings())["app_env"] == "test"


@pytest.mark.unit
def test_readiness_body_leaks_no_deployment_detail() -> None:
    """Unauthenticated endpoint: fixed vocabulary, no free text, no topology."""
    assert set(readiness_body("ok", _settings())) == {"status", "database", "app_env", "actuation"}


def _actuation_settings(*, writes: bool, substrate: str) -> Settings:
    """Settings with the two actuation inputs pinned; init kwargs beat the env."""
    return Settings(
        app_env="test",
        control_writes_enabled=writes,
        compute_substrate=substrate,  # type: ignore[arg-type]
    )


@pytest.mark.unit
def test_derive_actuation_reports_inert_when_both_paths_shut() -> None:
    """The observe-only default: writes off and compute cannot spawn."""
    assert derive_actuation(_actuation_settings(writes=False, substrate="in_memory")) == "inert"


@pytest.mark.unit
def test_derive_actuation_reachable_when_control_writes_on() -> None:
    assert derive_actuation(_actuation_settings(writes=True, substrate="in_memory")) == "reachable"


@pytest.mark.unit
def test_derive_actuation_reachable_when_compute_can_spawn() -> None:
    """The bypass path: local_process can run argv that reaches a control system."""
    assert (
        derive_actuation(_actuation_settings(writes=False, substrate="local_process"))
        == "reachable"
    )


@pytest.mark.unit
def test_derive_actuation_reachable_when_both_paths_open() -> None:
    assert (
        derive_actuation(_actuation_settings(writes=True, substrate="local_process")) == "reachable"
    )


@pytest.mark.unit
def test_readiness_body_reports_the_derived_actuation() -> None:
    inert = readiness_body("ok", _actuation_settings(writes=False, substrate="in_memory"))
    assert inert["actuation"] == "inert"
    reachable = readiness_body("ok", _actuation_settings(writes=True, substrate="in_memory"))
    assert reachable["actuation"] == "reachable"


@pytest.mark.unit
def test_readiness_body_actuation_is_independent_of_database_status() -> None:
    """A DB fault does not change the actuation posture; they are orthogonal."""
    body = readiness_body("unreachable", _actuation_settings(writes=False, substrate="in_memory"))
    assert body["status"] == "not_ready"
    assert body["actuation"] == "inert"

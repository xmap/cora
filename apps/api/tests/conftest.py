"""Pytest configuration and shared fixtures.

`APP_ENV=test` is set before any test imports so unit + contract tests
that build a FastAPI app via `create_app()` get the in-memory adapters
by default. Integration and e2e tests override this on a per-test
basis (integration: tests build their own Kernel against `db_pool`;
e2e: the `e2e_app` fixture monkeypatches `APP_ENV` + `DATABASE_URL`
so the lifespan picks the testcontainers Postgres branch).

## Session-scoped Postgres container (per xdist worker)

`postgres_container` and `template_database` live here (not in the
integration tier's conftest) so the integration `db_pool` fixture and
the e2e `e2e_app` fixture share one container per test session. The
template-DB clone strategy: migrations apply once into the container's
default DB; each per-test database is created via `CREATE DATABASE
... TEMPLATE migrated_db`, which Postgres satisfies via file copy in
tens of milliseconds.

Under pytest-xdist, each worker is a separate process and runs its own
session — so `scope="session"` naturally yields one container per
worker. The `worker_id` (`"master"` when not under xdist, else `gw0`,
`gw1`, ...) is woven into the container name purely for `docker ps`
debuggability. Sharing one container across xdist workers is a known
testcontainers-python footgun (issue #567: ports get reassigned to the
wrong instance during overlapping start/stop); per-worker containers
sidestep it entirely at the cost of ~2s container startup per worker.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

import asyncpg
import pytest
import pytest_asyncio
from hypothesis import HealthCheck, Verbosity, settings
from testcontainers.postgres import PostgresContainer

from tests._postgres import normalize_async_url

os.environ.setdefault("APP_ENV", "test")

# Control writes are OFF by default in production (the observe-only pilot
# posture); the test environment turns them ON, the same way APP_ENV=test
# relaxes the trust / auth / signing boot gates. Observe-only is a
# deployment safety default, not a property of the system, so the suite
# must exercise the full writable conduct surface. The default-is-safe
# behaviour is covered at the unit tier (build_control_port with
# writes_enabled=False), not by every app-level conduct test refusing.
# A test that asserts the SAFE default must build Settings ignoring this
# env override (e.g. Settings(_env_file=None) with the var cleared).
os.environ.setdefault("CONTROL_WRITES_ENABLED", "true")

# Hypothesis profiles for property-based testing.
# `dev` (default locally): keep the example database on, allow shrinking, default
#   max_examples — the fast feedback loop a developer wants.
# `ci`: derandomize the seed so xdist workers don't collide on the example
#   database, disable the example DB write entirely (avoids worker write
#   contention), drop the deadline so a slow CI runner doesn't flake, and
#   silence the function-scoped-fixture health check that trips on
#   pytest-asyncio's per-test event loop. Auto-activates when CI=true.
settings.register_profile("dev", deadline=None)
settings.register_profile(
    "ci",
    deadline=None,
    derandomize=True,
    database=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
    verbosity=Verbosity.normal,
)
settings.load_profile("ci" if os.environ.get("CI") == "true" else "dev")

# Repo-root/infra/atlas/migrations relative to this conftest.
_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "infra" / "atlas" / "migrations"


def _read_migration_statements() -> list[str]:
    """Read migration .sql files in order. Each file is executed as one batch."""
    files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    return [f.read_text() for f in files]


@pytest.fixture(scope="session")
def postgres_container(worker_id: str) -> Generator[PostgresContainer]:
    """One Postgres container per xdist worker (or one for the whole session
    when not under xdist). `worker_id` is `"master"` outside xdist; pytest-
    xdist provides the fixture and resolves it to `gw0`, `gw1`, ... per
    worker process."""
    container = PostgresContainer("pgvector/pgvector:pg18", driver=None)
    # Distinct container names per worker make `docker ps` legible during
    # debugging and prevent any accidental name collision if the suite is
    # interrupted mid-run.
    container.with_name(f"cora-pgtest-{worker_id}")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest_asyncio.fixture(scope="session")
async def template_database(postgres_container: PostgresContainer) -> str:
    """Apply migrations once per worker; the resulting DB is the clone template."""
    base_url = normalize_async_url(postgres_container.get_connection_url())
    template_name = urlparse(base_url).path.lstrip("/")

    conn = await asyncpg.connect(base_url)
    try:
        for sql in _read_migration_statements():
            await conn.execute(sql)
    finally:
        await conn.close()

    return template_name

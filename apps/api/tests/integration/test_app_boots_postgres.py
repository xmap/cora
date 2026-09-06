"""CORA starts. The one test that runs the real composition root.

Nothing else in the suite boots the app. Every `create_app()` test runs
`app_env=test`, which takes `build_kernel`'s in-memory branch, skips
`drain_projections` because there is no pool, and leaves the permissive
kernel defaults in place. So the Postgres branch of the composition root,
which is the branch a deployment actually walks, is executed for the first
time when someone deploys.

That branch is where startup does its real work: roughly thirty seed,
drain and register calls in a fixed order, each depending on what ran
before it. `test_seed_order_catalog_before_agents` guards two of those
orderings by reading `main.py` and asserting about the order of calls in
`main.py`, which cannot execute them. This test executes them.

## Why it drives the real entry point instead of repeating its steps

A test that reproduced the startup sequence would assert about its own
copy. Delete a line from `main.py` and the copy still has it, so the test
stays green while the deployment breaks. That is the same blindness as a
guard reading the file it guards, one level up.

Two unrelated ecosystems reached the same conclusion. Spring Boot builds
the test context through `SpringApplication`, the production path, and
offers `useMainMethod=ALWAYS` precisely for applications whose `main` does
work that affects the result. ASP.NET Core's `WebApplicationFactory` boots
the real entry point and runs test overrides AFTER the app's own
`Program.cs`, so swapping the database means finding and REMOVING the real
registration rather than never performing it. Both run the real root and
override one input.

That is what this does. `create_app`'s `settings` hook, which already
exists for exactly this purpose, redirects the database at a migrated
container. `app_env` stays `local`, so `build_kernel` takes the Postgres
branch (it branches `test` to in-memory and anything else to Postgres)
while staying clear of the production-tier hardening, which keys on
`{prod, production, staging}`. Everything else is the deployment's own
wiring, unmodified.

## Scope is deliberate: one boot, two assertions

Both sources above warn that broad tests become catch-alls that fail for
unrelated reasons and localise nothing. Microsoft's wording: limit them to
the most important infrastructure scenarios, and prefer a unit test
wherever either would do. So this file asks one question, "does it come
up", and leaves every WHY to the narrower tests. When it goes red, read
`test_language_model_catalog_chain_postgres` to find out which link broke.
Resist adding behavioural assertions here; they belong in the tier that
can localise them.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from collections.abc import Iterator
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from cora.api.main import create_app
from cora.infrastructure.config import Settings
from tests._postgres import normalize_async_url

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def deployment_database(
    postgres_container: PostgresContainer,
    template_database: str,
) -> object:
    """A migrated database of this deployment's own, given as a sync URL.

    Per-test rather than shared: startup writes the seed streams, and a
    second boot against the same database exercises idempotency instead of
    a fresh deployment, which is the case worth covering here.
    """
    test_db = f"boot_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(postgres_container.get_connection_url(), database="postgres")
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    yield normalize_async_url(postgres_container.get_connection_url(), database=test_db)

    admin = await asyncpg.connect(admin_url)
    try:
        # FORCE, unlike the sibling fixtures, because a boot that raises
        # partway leaves the app's pool open and a plain DROP then fails.
        # That turned a failing assertion into a failure plus a teardown
        # error, which is noise in exactly the run someone has to read.
        await admin.execute(f'DROP DATABASE "{test_db}" WITH (FORCE)')
    finally:
        await admin.close()


def _boot(database_url: str) -> Iterator[TestClient]:
    """Enter the real lifespan against `database_url`.

    `app_env=local` is the load-bearing choice: not `test`, so
    `build_kernel` opens a pool and runs the seeds, and not production-tier,
    so the auth and signing boot refusals stay out of the way. The database
    is the ONLY thing overridden.
    """
    settings = Settings(app_env="local", database_url=database_url)  # type: ignore[call-arg]
    with TestClient(create_app(settings=settings)) as client:
        yield client


async def test_the_app_boots_against_a_real_database(deployment_database: str) -> None:
    """Entering the lifespan IS the assertion.

    Every seed, drain and registration the composition root performs runs
    here, in its real order, against real Postgres. Any of them raising
    fails this test, which is the point: today they would raise at a
    deployment instead.
    """
    for client in _boot(deployment_database):
        response = client.get("/readyz")
        assert response.status_code == 200, (
            f"the app booted but does not report ready: {response.text}"
        )


async def test_a_second_boot_against_the_same_database_is_a_no_op(
    deployment_database: str,
) -> None:
    """Restarting a deployment must not be a first boot.

    The seeds are idempotent through `ConcurrencyError`, and every
    restart re-runs all of them. A seed that lost idempotency would pass
    the test above, which only ever sees an empty database, and strand a
    running deployment on its next restart.
    """
    for _ in _boot(deployment_database):
        pass

    for client in _boot(deployment_database):
        response = client.get("/readyz")
        assert response.status_code == 200, f"the app booted once but not twice: {response.text}"

"""The model-approval chain, joined up, against real Postgres.

Seeding a LanguageModel-brained Agent reaches its verdict through five
links: `seed_language_models` appends the catalog streams, the projection
turns those events into `proj_agent_language_model_summary` rows,
`drain_projections` advances the bookmark so the rows are visible,
`PostgresLanguageModelLookup` reads them, and `seed_agent`'s gate consumes
the answer. Every link already has a test. None of them crosses a join.

The clearest case is the adapter's own integration test, which populates
the read model by hand-written INSERT. That proves the SQL reads a correct
table; it cannot see whether anything fills it. And `drain_projections`
covering THIS projection is asserted nowhere at all: the two architecture
guards read `main.py` and assert about the order of calls in `main.py`, so
they can prove a drain sits between the two seeds and not that the drain
reaches the table the gate will read.

So this file asserts the joins rather than the links, reproducing the
composition root's real sequence (main.py's `seed_language_models` ->
`register_agent_projections` -> `drain_projections` -> `seed_*_agent`)
with the REAL `PostgresLanguageModelLookup` bound, which is the binding
`build_postgres_deps` otherwise leaves at the always-approved stub.

CautionDrafter is the subject because it is one of the two shipped agents
that declare a real Anthropic model, so it is one of the two whose boot a
broken chain actually stops.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from cora.agent import register_agent_projections
from cora.agent.adapters import PostgresLanguageModelLookup
from cora.agent.aggregates.agent.read import load_agent
from cora.agent.aggregates.language_model.state import LanguageModelNotApprovedError
from cora.agent.prompts.caution_drafter import DEFAULT_CAUTION_DRAFTER_MODEL
from cora.agent.seed_caution_drafter import (
    CAUTION_DRAFTER_AGENT_ID,
    seed_caution_drafter_agent,
)
from cora.agent.seed_language_models import seed_language_models
from cora.infrastructure.kernel import Kernel
from cora.infrastructure.postgres.pool import create_pool
from cora.infrastructure.projection.drain import drain_projections
from cora.infrastructure.projection.registry import ProjectionRegistry
from tests._postgres import normalize_async_url
from tests.integration._helpers import build_postgres_deps

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 9, 6, tzinfo=UTC)


@pytest_asyncio.fixture
async def chain_pool(
    postgres_container: PostgresContainer,
    template_database: str,
):
    """A per-test database, because the sequence under test writes the
    catalog streams and the read model the next link reads back."""
    test_db = f"lmchain_{uuid4().hex[:12]}"
    admin_url = normalize_async_url(postgres_container.get_connection_url(), database="postgres")
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{test_db}" TEMPLATE "{template_database}"')
    finally:
        await admin.close()

    test_url = normalize_async_url(postgres_container.get_connection_url(), database=test_db)
    pool = await create_pool(test_url, min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE "{test_db}"')
        finally:
            await admin.close()


def _kernel_with_the_real_lookup(pool: asyncpg.Pool) -> Kernel:
    """The gate's production binding, which every other test leaves as
    the always-approved stub. Without this the assertions below pass on
    any database, chain or no chain."""
    return build_postgres_deps(
        pool,
        now=_NOW,
        language_model_lookup=PostgresLanguageModelLookup(pool),
    )


async def _drain_the_catalog(pool: asyncpg.Pool, kernel: Kernel) -> None:
    """main.py's own three lines, verbatim in shape."""
    registry = ProjectionRegistry()
    register_agent_projections(registry, kernel)
    await drain_projections(pool, registry, deadline_seconds=5.0)


async def test_seeding_the_catalog_then_draining_admits_an_llm_brained_agent(
    chain_pool: asyncpg.Pool,
) -> None:
    """The whole sequence, end to end: after the catalog is seeded and
    drained, the gate reading the real projection admits the shipped
    agent whose brain is a real Anthropic model.

    This one passes under the always-approved stub too, so on its own it
    would not prove the gate was consulted at all. What makes it mean
    something is the test below: the same helper's kernel REFUSES when the
    read model is empty, so the admission here is the catalog answering
    rather than a stub agreeing. Read the two as a pair.
    """
    kernel = _kernel_with_the_real_lookup(chain_pool)

    await seed_language_models(kernel)
    await _drain_the_catalog(chain_pool, kernel)
    await seed_caution_drafter_agent(kernel)

    agent = await load_agent(kernel.event_store, CAUTION_DRAFTER_AGENT_ID)
    assert agent is not None, "the gate refused an agent whose model the catalog approves"


async def test_the_drain_is_what_makes_the_approval_visible(
    chain_pool: asyncpg.Pool,
) -> None:
    """The join the static guards cannot assert.

    Same sequence with the drain removed. The catalog streams exist, so
    every event the approval is derived from is already written; only the
    read model the gate consults is unpopulated. The gate must refuse,
    which is what makes the drain load-bearing rather than incidental.
    """
    kernel = _kernel_with_the_real_lookup(chain_pool)

    await seed_language_models(kernel)

    with pytest.raises(LanguageModelNotApprovedError):
        await seed_caution_drafter_agent(kernel)


async def test_the_drain_fills_the_read_model_the_gate_reads(
    chain_pool: asyncpg.Pool,
) -> None:
    """The middle join on its own, so a failure says WHICH link broke.

    The test above proves the gate refuses without a drain; this one
    proves the drain is what fills the specific identity the gate will
    ask for, rather than merely writing some rows.
    """
    kernel = _kernel_with_the_real_lookup(chain_pool)
    lookup = PostgresLanguageModelLookup(chain_pool)

    await seed_language_models(kernel)
    assert (
        await lookup.find_by_model(
            provider=DEFAULT_CAUTION_DRAFTER_MODEL.provider,
            model=DEFAULT_CAUTION_DRAFTER_MODEL.model,
        )
        is None
    ), "the read model answered before any drain ran"

    await _drain_the_catalog(chain_pool, kernel)

    entry = await lookup.find_by_model(
        provider=DEFAULT_CAUTION_DRAFTER_MODEL.provider,
        model=DEFAULT_CAUTION_DRAFTER_MODEL.model,
    )
    assert entry is not None, "the drain did not reach proj_agent_language_model_summary"
    assert entry.status == "Approved"

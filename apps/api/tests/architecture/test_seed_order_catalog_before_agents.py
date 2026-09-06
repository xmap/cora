"""Fitness: the LanguageModel catalog is seeded before any Agent.

`seed_agent` checks an LLM-brained Agent's model against the approved catalog,
the same check `define_agent` applies to an operator. That check reads
`proj_agent_language_model_summary`, so on a fresh Postgres deployment the
catalog must be seeded AND drained before the first Agent seed runs, or boot
fails with two agents checked against an empty catalog.

## Why this is a static guard rather than a test that boots the app

Nothing in the suite boots the full app against a real pool: every
`create_app()` test runs in-memory, where `drain_projections` is skipped
(`deps.pool is None`) and the Kernel's default
`AlwaysApprovedLanguageModelLookup` passes everything. So the ordering this
guards cannot be observed by running the app in tests, only by reading the
composition root. That makes the ordering exactly the kind of invariant that
rots silently, which is what a fitness function is for.

The order used to be the reverse, and worked only because the seeds bypassed
the gate: the catalog was seeded after the fleet it was supposed to gate. The
bypass and the ordering propped each other up, so closing one required fixing
the other.
"""

import re

from tests.architecture.conftest import CORA_ROOT

_MAIN = CORA_ROOT / "api" / "main.py"

_CATALOG_SEED = re.compile(r"^\s*await seed_language_models\(", re.M)
_AGENT_SEED = re.compile(r"^\s*await seed_\w*_agent\(", re.M)
_DRAIN = re.compile(r"^\s*await drain_projections\(", re.M)


def test_language_model_catalog_is_seeded_before_the_first_agent() -> None:
    source = _MAIN.read_text()

    catalog = _CATALOG_SEED.search(source)
    first_agent = _AGENT_SEED.search(source)

    assert catalog is not None, "main.py no longer seeds the LanguageModel catalog"
    assert first_agent is not None, "main.py no longer seeds any Agent"
    assert catalog.start() < first_agent.start(), (
        "seed_language_models must run BEFORE the first seed_*_agent call. "
        "seed_agent gates an LLM-brained Agent against the approved catalog, so "
        "seeding agents first refuses boot on a fresh deployment with two agents "
        "checked against an empty catalog."
    )


def test_the_catalog_is_drained_before_the_first_agent() -> None:
    """Seeding it is not enough: the gate reads a projection.

    `PostgresLanguageModelLookup` reads `proj_agent_language_model_summary`,
    which the worker populates asynchronously. Without a synchronous drain
    between the catalog seed and the first Agent seed, a fresh Postgres boot
    races the worker and refuses agents whose models were just approved.
    """
    source = _MAIN.read_text()

    catalog = _CATALOG_SEED.search(source)
    first_agent = _AGENT_SEED.search(source)
    assert catalog is not None and first_agent is not None

    drains_between = [
        match
        for match in _DRAIN.finditer(source)
        if catalog.start() < match.start() < first_agent.start()
    ]
    assert drains_between, (
        "no drain_projections call between seed_language_models and the first "
        "seed_*_agent call. The approval gate reads a projection, so the catalog "
        "must be visible before the agents that depend on it are seeded."
    )

"""Property-based tests for `InMemoryAssetLookup.ancestors_of` (chain-walk Anti-hook 3c).

Hypothesis-driven exploration of the ancestor-walk over random
single-parent forests, with cycles injected by construction. Validates
two invariants example-based tests can't blanket:

  - acyclic forest: the walk returns EXACTLY the inclusive ancestor
    closure of the query set, matching an independent reference
    implementation (the oracle), for any forest shape + any query subset;
  - any reachable cycle: the walk RAISES `AncestorWalkDepthExceededError`
    rather than looping or truncating, for any cycle reachable from the
    query.

Per the repo's PBT grain (see `tests/unit/test_event_store_property.py`):
PBT runs against the IN-MEMORY adapter only -- it is the spec
implementation, fast enough for hundreds of generated cases in the unit
tier and free of an event-loop-bound asyncpg pool. Parity between the
in-memory spec and the Postgres recursive-CTE adapter is ensured
SEPARATELY by the example-based integration suite
(`tests/integration/test_postgres_asset_lookup_ancestors.py`), which
mirrors these same shapes (inclusive closure, shared ancestor, disjoint
forests, missing mid-chain, self-loop, multi-level cycle, climb-into-
cycle, depth overrun). So the "both adapters agree, both raise on
cyclic" guarantee holds across the two tiers in the repo's idiom rather
than via a Hypothesis-over-Postgres test the repo deliberately avoids.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.ports.asset_lookup import AncestorWalkDepthExceededError


def _uid(index: int) -> UUID:
    """Deterministic, collision-free UUID for a node label."""
    return UUID(int=index + 1)


def _reference_closure(parents: list[int | None], query: list[int]) -> set[int]:
    """Independent oracle: inclusive ancestor closure by naive climbing.

    Mirrors the adapter contract (include the input nodes, climb each
    parent to None, dedup) without sharing the adapter's code, so a bug
    in the adapter cannot hide behind a matching bug in the oracle.
    """
    collected: set[int] = set()
    for start in query:
        current: int | None = start
        while current is not None and current not in collected:
            collected.add(current)
            current = parents[current]
    return collected


@st.composite
def _acyclic_forest(draw: st.DrawFn) -> tuple[list[int | None], list[int]]:
    """A single-parent forest + a non-empty query subset.

    Node `i`'s parent is drawn from `{None} | {0..i-1}` -- a strictly
    earlier index -- which makes the forest acyclic by construction
    (every parent edge points to a lower label).
    """
    n = draw(st.integers(min_value=1, max_value=8))
    parents: list[int | None] = [draw(st.sampled_from([None, *range(i)])) for i in range(n)]
    query = draw(st.lists(st.integers(min_value=0, max_value=n - 1), min_size=1, unique=True))
    return parents, query


@st.composite
def _forest_with_reachable_cycle(draw: st.DrawFn) -> tuple[list[int | None], int]:
    """An acyclic forest mutated so a cycle is reachable from node `a`.

    Build acyclic parents, pick a node `a`, then pick a node `r` on `a`'s
    upward chain (possibly `a` itself) and redirect `parents[r] = a`. Now
    `a -> ... -> r -> a` is a cycle, and it is reachable by walking up
    from `a`. For a single node this degenerates to a self-loop. Every
    generated example is therefore genuinely cyclic.
    """
    n = draw(st.integers(min_value=1, max_value=8))
    parents: list[int | None] = [draw(st.sampled_from([None, *range(i)])) for i in range(n)]
    a = draw(st.integers(min_value=0, max_value=n - 1))

    chain: list[int] = []
    current: int | None = a
    while current is not None:
        chain.append(current)
        current = parents[current]

    r = draw(st.sampled_from(chain))
    parents[r] = a
    return parents, a


def _build(parents: list[int | None]) -> InMemoryAssetLookup:
    lookup = InMemoryAssetLookup()
    for i, parent in enumerate(parents):
        lookup.register(
            _uid(i),
            name=f"a{i}",
            parent_id=_uid(parent) if parent is not None else None,
        )
    return lookup


@pytest.mark.unit
@given(forest=_acyclic_forest())
async def test_ancestors_of_acyclic_forest_matches_reference_closure(
    forest: tuple[list[int | None], list[int]],
) -> None:
    parents, query = forest
    lookup = _build(parents)

    result = await lookup.ancestors_of(frozenset(_uid(q) for q in query))

    assert {r.id for r in result} == {_uid(c) for c in _reference_closure(parents, query)}


@pytest.mark.unit
@given(forest=_forest_with_reachable_cycle())
async def test_ancestors_of_any_reachable_cycle_raises(
    forest: tuple[list[int | None], int],
) -> None:
    parents, a = forest
    lookup = _build(parents)

    with pytest.raises(AncestorWalkDepthExceededError):
        await lookup.ancestors_of(frozenset({_uid(a)}))

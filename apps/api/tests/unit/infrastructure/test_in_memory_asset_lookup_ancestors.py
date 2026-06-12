"""Unit tests for `InMemoryAssetLookup.ancestors_of`.

Pins the in-memory parent-chain walk: inclusive closure, single-parent
tree termination at a root (`parent_id is None`), shared-ancestor and
ancestor-input dedup without false cycle-raises, missing-row
termination, and loud failure (never truncate-and-return) on a
`parent_id` cycle or an over-deep chain. This adapter is the parity
reference for the Postgres recursive-CTE adapter.
"""

from uuid import UUID, uuid4

import pytest

from cora.infrastructure.adapters.in_memory_asset_lookup import InMemoryAssetLookup
from cora.infrastructure.ports.asset_lookup import (
    ANCESTOR_WALK_DEPTH_CAP,
    AncestorWalkDepthExceededError,
)


def _ids(result: frozenset[object]) -> set[UUID]:
    return {r.id for r in result}  # type: ignore[attr-defined]


@pytest.mark.unit
async def test_ancestors_of_empty_input_returns_empty() -> None:
    lookup = InMemoryAssetLookup()
    assert await lookup.ancestors_of(frozenset()) == frozenset()


@pytest.mark.unit
async def test_ancestors_of_root_only_returns_just_the_root() -> None:
    lookup = InMemoryAssetLookup()
    root = uuid4()
    lookup.register(root, name="2-BM", tier="Unit", parent_id=None)
    assert _ids(await lookup.ancestors_of(frozenset({root}))) == {root}


@pytest.mark.unit
async def test_ancestors_of_device_includes_self_and_root() -> None:
    lookup = InMemoryAssetLookup()
    root, device = uuid4(), uuid4()
    lookup.register(root, name="2-BM", tier="Unit", parent_id=None)
    lookup.register(device, name="rotary", tier="Device", parent_id=root)
    assert _ids(await lookup.ancestors_of(frozenset({device}))) == {device, root}


@pytest.mark.unit
async def test_ancestors_of_shared_ancestor_dedups_without_raising() -> None:
    lookup = InMemoryAssetLookup()
    root, d1, d2 = uuid4(), uuid4(), uuid4()
    lookup.register(root, name="2-BM", tier="Unit", parent_id=None)
    lookup.register(d1, name="rotary", tier="Device", parent_id=root)
    lookup.register(d2, name="camera", tier="Device", parent_id=root)
    assert _ids(await lookup.ancestors_of(frozenset({d1, d2}))) == {d1, d2, root}


@pytest.mark.unit
async def test_ancestors_of_input_that_is_ancestor_of_another_input_no_false_raise() -> None:
    # Regression: an input id that is itself an ancestor of another
    # input id must not trigger a false cycle-raise (the walk
    # short-circuits on the shared-accumulator hit, not a path revisit).
    lookup = InMemoryAssetLookup()
    root, device = uuid4(), uuid4()
    lookup.register(root, name="2-BM", tier="Unit", parent_id=None)
    lookup.register(device, name="rotary", tier="Device", parent_id=root)
    assert _ids(await lookup.ancestors_of(frozenset({device, root}))) == {device, root}


@pytest.mark.unit
async def test_ancestors_of_missing_input_row_contributes_nothing() -> None:
    lookup = InMemoryAssetLookup()
    root, device = uuid4(), uuid4()
    ghost = uuid4()
    lookup.register(root, name="2-BM", tier="Unit", parent_id=None)
    lookup.register(device, name="rotary", tier="Device", parent_id=root)
    assert _ids(await lookup.ancestors_of(frozenset({device, ghost}))) == {device, root}


@pytest.mark.unit
async def test_ancestors_of_missing_mid_chain_parent_terminates() -> None:
    # A parent_id pointing at an id with no projection row terminates
    # the climb at the last present row (eventual-consistency tolerance).
    lookup = InMemoryAssetLookup()
    device, absent_parent = uuid4(), uuid4()
    lookup.register(device, name="rotary", tier="Device", parent_id=absent_parent)
    assert _ids(await lookup.ancestors_of(frozenset({device}))) == {device}


@pytest.mark.unit
async def test_ancestors_of_two_cycle_raises() -> None:
    lookup = InMemoryAssetLookup()
    a, b = uuid4(), uuid4()
    lookup.register(a, name="a", tier="Device", parent_id=b)
    lookup.register(b, name="b", tier="Device", parent_id=a)
    with pytest.raises(AncestorWalkDepthExceededError):
        await lookup.ancestors_of(frozenset({a}))


@pytest.mark.unit
async def test_ancestors_of_self_loop_raises() -> None:
    lookup = InMemoryAssetLookup()
    a = uuid4()
    lookup.register(a, name="a", tier="Device", parent_id=a)
    with pytest.raises(AncestorWalkDepthExceededError):
        await lookup.ancestors_of(frozenset({a}))


@pytest.mark.unit
async def test_ancestors_of_chain_deeper_than_cap_raises() -> None:
    lookup = InMemoryAssetLookup()
    ids = [uuid4() for _ in range(ANCESTOR_WALK_DEPTH_CAP + 5)]
    # Build a straight chain ids[0] -> ids[1] -> ... -> ids[-1] (root).
    for i, asset_id in enumerate(ids):
        parent = ids[i + 1] if i + 1 < len(ids) else None
        lookup.register(asset_id, name=f"n{i}", tier="Device", parent_id=parent)
    with pytest.raises(AncestorWalkDepthExceededError):
        await lookup.ancestors_of(frozenset({ids[0]}))


@pytest.mark.unit
async def test_ancestors_of_chain_at_cap_succeeds() -> None:
    # A legitimate chain at the cap boundary resolves without raising.
    lookup = InMemoryAssetLookup()
    depth = ANCESTOR_WALK_DEPTH_CAP - 1
    ids = [uuid4() for _ in range(depth)]
    for i, asset_id in enumerate(ids):
        parent = ids[i + 1] if i + 1 < len(ids) else None
        lookup.register(asset_id, name=f"n{i}", tier="Device", parent_id=parent)
    assert _ids(await lookup.ancestors_of(frozenset({ids[0]}))) == set(ids)

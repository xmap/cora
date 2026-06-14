"""End-to-end: `PostgresAssetLookup.ancestors_of` recursive-CTE walk.

Pins the parent_id ancestor walk against real Postgres: inclusive
closure to the facility-rooted root, shared-ancestor dedup, and loud
failure (never a wrong partial closure) on a cycle (the SQL-standard
CYCLE clause, the load-bearing terminator) or a depth overrun (the
ANCESTOR_WALK_DEPTH_CAP belt-and-braces ceiling). Seeds the Asset
projection by appending synthetic AssetRegistered events with the
parent_id chain under test, then draining the equipment projections.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.equipment.adapters.postgres_asset_lookup import PostgresAssetLookup
from cora.infrastructure.adapters.postgres_event_store import PostgresEventStore
from cora.infrastructure.ports.asset_lookup import AncestorWalkDepthExceededError
from cora.infrastructure.ports.event_store import NewEvent
from tests.integration._equipment_helpers import drain_equipment_projections

_NOW = datetime(2026, 6, 12, 9, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")

_CAP_PATH = "cora.equipment.adapters.postgres_asset_lookup.ANCESTOR_WALK_DEPTH_CAP"


async def _register_asset(
    pool: asyncpg.Pool,
    *,
    asset_id: UUID,
    parent_id: UUID | None,
    name: str = "synthetic-asset",
    tier: str = "Device",
    located_in_enclosure_id: UUID | None = None,
) -> None:
    """Append a synthetic AssetRegistered with the given parent edge + drain."""
    store = PostgresEventStore(pool)
    payload: dict[str, object] = {
        "asset_id": str(asset_id),
        "name": name,
        "tier": tier,
        "parent_id": str(parent_id) if parent_id is not None else None,
        "occurred_at": _NOW.isoformat(),
        "commissioned_by": str(_PRINCIPAL_ID),
    }
    if located_in_enclosure_id is not None:
        payload["located_in_enclosure_id"] = str(located_in_enclosure_id)
    await store.append(
        "Asset",
        asset_id,
        0,
        [
            NewEvent(
                event_id=uuid4(),
                event_type="AssetRegistered",
                schema_version=1,
                payload=payload,
                occurred_at=_NOW,
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                metadata={},
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )
    await drain_equipment_projections(pool)


def _ids(result: frozenset[object]) -> set[UUID]:
    return {r.id for r in result}  # type: ignore[attr-defined]


def _by_id(result: frozenset[object]) -> dict[UUID, object]:
    return {r.id: r for r in result}  # type: ignore[attr-defined]


@pytest.mark.integration
async def test_ancestors_of_returns_inclusive_closure_to_root(db_pool: asyncpg.Pool) -> None:
    root, mid, leaf = uuid4(), uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=root, parent_id=None, tier="Unit")
    await _register_asset(db_pool, asset_id=mid, parent_id=root, tier="Component")
    await _register_asset(db_pool, asset_id=leaf, parent_id=mid, tier="Device")

    lookup = PostgresAssetLookup(db_pool)
    result = await lookup.ancestors_of(frozenset({leaf}))
    assert _ids(result) == {leaf, mid, root}


@pytest.mark.integration
async def test_ancestors_of_root_returns_just_root(db_pool: asyncpg.Pool) -> None:
    root = uuid4()
    await _register_asset(db_pool, asset_id=root, parent_id=None, tier="Unit")

    lookup = PostgresAssetLookup(db_pool)
    assert _ids(await lookup.ancestors_of(frozenset({root}))) == {root}


@pytest.mark.integration
async def test_ancestors_of_shared_ancestor_dedups(db_pool: asyncpg.Pool) -> None:
    root, d1, d2 = uuid4(), uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=root, parent_id=None, tier="Unit")
    await _register_asset(db_pool, asset_id=d1, parent_id=root, tier="Device")
    await _register_asset(db_pool, asset_id=d2, parent_id=root, tier="Device")

    lookup = PostgresAssetLookup(db_pool)
    assert _ids(await lookup.ancestors_of(frozenset({d1, d2}))) == {d1, d2, root}


@pytest.mark.integration
async def test_ancestors_of_empty_input_returns_empty(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresAssetLookup(db_pool)
    assert await lookup.ancestors_of(frozenset()) == frozenset()


@pytest.mark.integration
async def test_ancestors_of_unknown_input_returns_empty(db_pool: asyncpg.Pool) -> None:
    lookup = PostgresAssetLookup(db_pool)
    assert await lookup.ancestors_of(frozenset({uuid4()})) == frozenset()


@pytest.mark.integration
async def test_ancestors_of_four_level_cycle_raises_via_cycle_clause(
    db_pool: asyncpg.Pool,
) -> None:
    # 3a: a -> b -> c -> d -> a. The CYCLE clause terminates the
    # recursion (no hang; if it did not, pytest-timeout would fail the
    # test) and the adapter raises rather than returning a partial set.
    a, b, c, d = uuid4(), uuid4(), uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=a, parent_id=b)
    await _register_asset(db_pool, asset_id=b, parent_id=c)
    await _register_asset(db_pool, asset_id=c, parent_id=d)
    await _register_asset(db_pool, asset_id=d, parent_id=a)

    lookup = PostgresAssetLookup(db_pool)
    with pytest.raises(AncestorWalkDepthExceededError):
        await lookup.ancestors_of(frozenset({a}))


@pytest.mark.integration
async def test_ancestors_of_two_cycle_raises_independent_of_high_cap(
    db_pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 3b: with the depth cap raised far above the cycle length, the
    # CYCLE clause (not the cap) is what terminates and triggers the
    # raise -- proving the cycle terminator is independent of the cap.
    monkeypatch.setattr(_CAP_PATH, 1000)
    a, b = uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=a, parent_id=b)
    await _register_asset(db_pool, asset_id=b, parent_id=a)

    lookup = PostgresAssetLookup(db_pool)
    with pytest.raises(AncestorWalkDepthExceededError) as excinfo:
        await lookup.ancestors_of(frozenset({a}))
    # The error reports the depth at which the cycle was DETECTED (small),
    # not the cap (1000). That gap is exactly the operator-triage signal:
    # observed_depth << cap means a cycle, observed_depth == cap means a
    # legitimate-but-too-deep tree.
    assert excinfo.value.cap == 1000
    assert excinfo.value.observed_depth < 10


@pytest.mark.integration
async def test_ancestors_of_chain_past_cap_raises_overrun(
    db_pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Acyclic chain deeper than the cap raises via the depth-overrun
    # flag (a row at the cap depth still has an unwalked parent).
    monkeypatch.setattr(_CAP_PATH, 3)
    ids = [uuid4() for _ in range(6)]
    for i, asset_id in enumerate(ids):
        parent = ids[i + 1] if i + 1 < len(ids) else None
        await _register_asset(db_pool, asset_id=asset_id, parent_id=parent)

    lookup = PostgresAssetLookup(db_pool)
    with pytest.raises(AncestorWalkDepthExceededError) as excinfo:
        await lookup.ancestors_of(frozenset({ids[0]}))
    # An overrun (acyclic but past the cap) reports observed_depth == cap:
    # the walk reached the ceiling while a parent edge still dangled.
    assert excinfo.value.observed_depth == 3
    assert excinfo.value.cap == 3


@pytest.mark.integration
async def test_ancestors_of_chain_within_cap_succeeds(
    db_pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_CAP_PATH, 10)
    ids = [uuid4() for _ in range(5)]
    for i, asset_id in enumerate(ids):
        parent = ids[i + 1] if i + 1 < len(ids) else None
        await _register_asset(db_pool, asset_id=asset_id, parent_id=parent)

    lookup = PostgresAssetLookup(db_pool)
    assert _ids(await lookup.ancestors_of(frozenset({ids[0]}))) == set(ids)


@pytest.mark.integration
async def test_ancestors_of_hydrates_each_closure_row_not_just_ids(
    db_pool: asyncpg.Pool,
) -> None:
    # The closure SELECT re-joins the summary table per row; a regression
    # there (dropped tier, GROUP BY fan-out, wrong row) would still
    # return the right id set but corrupt the snapshot. Assert the full
    # row content for every level, not just the ids.
    root, mid, leaf = uuid4(), uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=root, parent_id=None, name="beamline", tier="Unit")
    await _register_asset(db_pool, asset_id=mid, parent_id=root, name="stage", tier="Component")
    await _register_asset(db_pool, asset_id=leaf, parent_id=mid, name="camera", tier="Device")

    lookup = PostgresAssetLookup(db_pool)
    rows = _by_id(await lookup.ancestors_of(frozenset({leaf})))

    # AssetRegistered projects lifecycle=Commissioned (the genesis state);
    # no membership events were appended, so affordances are empty.
    assert {(r.name, r.tier, r.lifecycle, r.family_affordances) for r in rows.values()} == {  # type: ignore[attr-defined]
        ("beamline", "Unit", "Commissioned", frozenset()),
        ("stage", "Component", "Commissioned", frozenset()),
        ("camera", "Device", "Commissioned", frozenset()),
    }


@pytest.mark.integration
async def test_lookup_returns_located_in_enclosure_id(db_pool: asyncpg.Pool) -> None:
    # The single-id lookup must surface the operational enclosure-zone
    # pointer written at registration so the enclosure pre-flight gate
    # reads it in one hop.
    asset_id, enclosure_id = uuid4(), uuid4()
    await _register_asset(
        db_pool,
        asset_id=asset_id,
        parent_id=None,
        tier="Unit",
        located_in_enclosure_id=enclosure_id,
    )

    lookup = PostgresAssetLookup(db_pool)
    result = await lookup.lookup(asset_id)
    assert result is not None
    assert result.located_in_enclosure_id == enclosure_id


@pytest.mark.integration
async def test_lookup_without_enclosure_yields_none(db_pool: asyncpg.Pool) -> None:
    asset_id = uuid4()
    await _register_asset(db_pool, asset_id=asset_id, parent_id=None, tier="Unit")

    lookup = PostgresAssetLookup(db_pool)
    result = await lookup.lookup(asset_id)
    assert result is not None
    assert result.located_in_enclosure_id is None


@pytest.mark.integration
async def test_ancestors_of_rows_carry_located_in_enclosure_id(db_pool: asyncpg.Pool) -> None:
    # Each closure row re-joins the summary table, so each must surface
    # its own located_in_enclosure_id; the recursive walk must not drop
    # the column in the GROUP BY fan-in.
    root, device = uuid4(), uuid4()
    root_enclosure, device_enclosure = uuid4(), uuid4()
    await _register_asset(
        db_pool,
        asset_id=root,
        parent_id=None,
        tier="Unit",
        located_in_enclosure_id=root_enclosure,
    )
    await _register_asset(
        db_pool,
        asset_id=device,
        parent_id=root,
        tier="Device",
        located_in_enclosure_id=device_enclosure,
    )

    lookup = PostgresAssetLookup(db_pool)
    rows = _by_id(await lookup.ancestors_of(frozenset({device})))
    assert rows[device].located_in_enclosure_id == device_enclosure  # type: ignore[attr-defined]
    assert rows[root].located_in_enclosure_id == root_enclosure  # type: ignore[attr-defined]


@pytest.mark.integration
async def test_ancestors_of_input_that_is_ancestor_of_another_input_does_not_raise(
    db_pool: asyncpg.Pool,
) -> None:
    # Passing both a leaf AND its own ancestor: the ancestor appears as a
    # seed (depth 0) and as the leaf's climbed parent (depth 1) on two
    # SEPARATE paths. The CYCLE clause keys on per-path asset_id
    # repetition, so two disjoint paths sharing a node must NOT false-raise.
    root, leaf = uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=root, parent_id=None, tier="Unit")
    await _register_asset(db_pool, asset_id=leaf, parent_id=root, tier="Device")

    lookup = PostgresAssetLookup(db_pool)
    assert _ids(await lookup.ancestors_of(frozenset({leaf, root}))) == {leaf, root}


@pytest.mark.integration
async def test_ancestors_of_disjoint_trees_return_both_closures(
    db_pool: asyncpg.Pool,
) -> None:
    root_a, leaf_a = uuid4(), uuid4()
    root_b, leaf_b = uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=root_a, parent_id=None, tier="Unit")
    await _register_asset(db_pool, asset_id=leaf_a, parent_id=root_a, tier="Device")
    await _register_asset(db_pool, asset_id=root_b, parent_id=None, tier="Unit")
    await _register_asset(db_pool, asset_id=leaf_b, parent_id=root_b, tier="Device")

    lookup = PostgresAssetLookup(db_pool)
    result = _ids(await lookup.ancestors_of(frozenset({leaf_a, leaf_b})))
    assert result == {root_a, leaf_a, root_b, leaf_b}


@pytest.mark.integration
async def test_ancestors_of_missing_mid_chain_parent_terminates_cleanly(
    db_pool: asyncpg.Pool,
) -> None:
    # mid points at a parent whose projection row never landed (eventual
    # consistency, or the parent was hard-deleted). The climb ends at the
    # gap and returns the partial-to-the-gap closure -- it does NOT raise.
    # This is the intended tolerance, distinct from the cap/cycle failure:
    # an absent row is a genuine chain end, not a runaway.
    leaf, mid, absent = uuid4(), uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=leaf, parent_id=mid, tier="Device")
    await _register_asset(db_pool, asset_id=mid, parent_id=absent, tier="Component")

    lookup = PostgresAssetLookup(db_pool)
    assert _ids(await lookup.ancestors_of(frozenset({leaf}))) == {leaf, mid}


@pytest.mark.integration
async def test_ancestors_of_self_loop_raises(db_pool: asyncpg.Pool) -> None:
    # A self-referential row (parent_id == own id) is the tightest cycle.
    # The CYCLE clause must catch it; the closure is non-empty so the
    # `if not rows` short-circuit cannot swallow the cycle flag.
    loop = uuid4()
    await _register_asset(db_pool, asset_id=loop, parent_id=loop)

    lookup = PostgresAssetLookup(db_pool)
    with pytest.raises(AncestorWalkDepthExceededError):
        await lookup.ancestors_of(frozenset({loop}))


@pytest.mark.integration
async def test_ancestors_of_acyclic_seed_climbing_into_a_cycle_raises(
    db_pool: asyncpg.Pool,
) -> None:
    # The input is acyclic, but its chain climbs INTO a cycle higher up:
    # leaf -> m -> x -> y -> x. The cycle is above the seed, not at it.
    leaf, m, x, y = uuid4(), uuid4(), uuid4(), uuid4()
    await _register_asset(db_pool, asset_id=leaf, parent_id=m)
    await _register_asset(db_pool, asset_id=m, parent_id=x)
    await _register_asset(db_pool, asset_id=x, parent_id=y)
    await _register_asset(db_pool, asset_id=y, parent_id=x)

    lookup = PostgresAssetLookup(db_pool)
    with pytest.raises(AncestorWalkDepthExceededError):
        await lookup.ancestors_of(frozenset({leaf}))


@pytest.mark.integration
async def test_ancestors_of_root_exactly_at_cap_depth_succeeds(
    db_pool: asyncpg.Pool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Boundary pin: a root sitting EXACTLY at depth == cap must succeed,
    # not false-raise. cap=3, chain of 4 (root at depth 3). The overrun
    # flag is `depth >= cap AND parent_id IS NOT NULL`; the root's
    # parent_id is NULL, so depth==cap alone does not trip it.
    monkeypatch.setattr(_CAP_PATH, 3)
    ids = [uuid4() for _ in range(4)]
    for i, asset_id in enumerate(ids):
        parent = ids[i + 1] if i + 1 < len(ids) else None
        await _register_asset(db_pool, asset_id=asset_id, parent_id=parent)

    lookup = PostgresAssetLookup(db_pool)
    assert _ids(await lookup.ancestors_of(frozenset({ids[0]}))) == set(ids)

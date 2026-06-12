"""In-memory `AssetLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` + `ancestors_of`
operations, same None-on-missing semantics, same
`AncestorWalkDepthExceededError` on a `parent_id` cycle or an
over-deep chain. A `threading.Lock` guards the dicts so concurrent
tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresAssetLookup` in `cora.equipment.adapters` is the
production option, reading `proj_equipment_asset_summary`).
"""

from collections.abc import Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.asset_lookup import (
    ANCESTOR_WALK_DEPTH_CAP,
    AncestorWalkDepthExceededError,
    AssetLookupResult,
)


class InMemoryAssetLookup:
    """Thread-safe in-memory implementation of the `AssetLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, AssetLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, AssetLookupResult] = dict(seed) if seed is not None else {}
        self._parents: dict[UUID, UUID | None] = {}
        self._lock = Lock()

    def register(
        self,
        asset_id: UUID,
        name: str,
        tier: str = "Unit",
        lifecycle: str = "Active",
        family_affordances: frozenset[str] | None = None,
        parent_id: UUID | None = None,
    ) -> None:
        """Test helper: install an asset summary keyed by `asset_id`.

        Default `tier="Unit"` matches the most common beamline-tier
        binding shape; tests for Component / Device cases pass the tier
        explicitly. Default `lifecycle="Active"` matches the post-
        commissioning steady-state. Default `family_affordances=None`
        seeds an empty set; affordance-gated consumers (Data BC
        `record_acquisition` Capturing gate) pass an explicit set.

        `parent_id` seeds the parent-chain edge `ancestors_of` walks;
        default `None` registers a root (facility-rooted) Asset, which
        keeps the existing single-arg callers untouched. Pass a
        non-null `parent_id` to register a sub-Asset whose chain walks
        up to its root.
        """
        with self._lock:
            self._records[asset_id] = AssetLookupResult(
                id=asset_id,
                name=name,
                tier=tier,
                lifecycle=lifecycle,
                family_affordances=(
                    family_affordances if family_affordances is not None else frozenset[str]()
                ),
            )
            self._parents[asset_id] = parent_id

    async def lookup(self, asset_id: UUID) -> AssetLookupResult | None:
        with self._lock:
            return self._records.get(asset_id)

    async def ancestors_of(self, asset_ids: frozenset[UUID]) -> frozenset[AssetLookupResult]:
        """Return the inclusive ancestor closure by walking `parent_id`.

        Climbs each input id's parent chain individually (single-parent
        tree, so each climb is a linked-list ascent), collecting every
        Asset that has a projection row into a shared accumulator,
        terminating at `parent_id is None` (a root) or at an id with no
        row. Cycle detection is per-climb: a node revisited on the
        CURRENT climb's path (for example A -> B -> A) raises
        `AncestorWalkDepthExceededError`; so does a climb deeper than
        `ANCESTOR_WALK_DEPTH_CAP`. The closure is NEVER
        truncated-and-returned. A node already in the shared
        accumulator short-circuits the climb (its chain was fully
        walked by a prior input id, so it is acyclic above this point):
        this keeps a shared ancestor, or an input id that is itself an
        ancestor of another input id, from false-raising. Empty input
        returns the empty frozenset. Mirrors the Postgres adapter's
        recursive CTE + CYCLE clause so adapter-parity tests hold.
        """
        if not asset_ids:
            return frozenset()
        with self._lock:
            collected: dict[UUID, AssetLookupResult] = {}
            for start in asset_ids:
                path: set[UUID] = set()
                current: UUID | None = start
                depth = 0
                while current is not None:
                    if current in path:
                        raise AncestorWalkDepthExceededError(
                            observed_depth=depth, cap=ANCESTOR_WALK_DEPTH_CAP
                        )
                    if current in collected:
                        break
                    if depth > ANCESTOR_WALK_DEPTH_CAP:
                        raise AncestorWalkDepthExceededError(
                            observed_depth=depth, cap=ANCESTOR_WALK_DEPTH_CAP
                        )
                    path.add(current)
                    row = self._records.get(current)
                    if row is None:
                        break
                    collected[current] = row
                    current = self._parents.get(current)
                    depth += 1
            return frozenset(collected.values())


__all__ = ["InMemoryAssetLookup"]

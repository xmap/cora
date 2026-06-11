"""In-memory `AssetLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` operation,
same None-on-missing semantics. A `threading.Lock` guards the dict
so concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresAssetLookup` in `cora.equipment.adapters` is the
production option, reading `proj_equipment_asset_summary`).
"""

from collections.abc import Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.asset_lookup import AssetLookupResult


class InMemoryAssetLookup:
    """Thread-safe in-memory implementation of the `AssetLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, AssetLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, AssetLookupResult] = dict(seed) if seed is not None else {}
        self._lock = Lock()

    def register(
        self,
        asset_id: UUID,
        name: str,
        tier: str = "Unit",
        lifecycle: str = "Active",
        family_affordances: frozenset[str] | None = None,
    ) -> None:
        """Test helper: install an asset summary keyed by `asset_id`.

        Default `tier="Unit"` matches the most common beamline-tier
        binding shape; tests for Component / Device cases pass the tier
        explicitly. Default `lifecycle="Active"` matches the post-
        commissioning steady-state. Default `family_affordances=None`
        seeds an empty set; affordance-gated consumers (Data BC
        `record_acquisition` Capturing gate) pass an explicit set.
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

    async def lookup(self, asset_id: UUID) -> AssetLookupResult | None:
        with self._lock:
            return self._records.get(asset_id)


__all__ = ["InMemoryAssetLookup"]

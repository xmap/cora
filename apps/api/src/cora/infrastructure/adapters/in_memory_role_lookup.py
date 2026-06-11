"""In-memory `RoleLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` operation,
same None-on-missing semantics. A `threading.Lock` guards the dict
so concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresRoleLookup` in `cora.equipment.adapters` is the production
option, reading `proj_equipment_role_summary`).
"""

from collections.abc import Iterable, Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.role_lookup import RoleLookupResult


class InMemoryRoleLookup:
    """Thread-safe in-memory implementation of the `RoleLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, RoleLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, RoleLookupResult] = dict(seed) if seed is not None else {}
        self._lock = Lock()

    def register(
        self,
        role_id: UUID,
        name: str,
        required_affordances: Iterable[str] = (),
        optional_affordances: Iterable[str] = (),
    ) -> None:
        """Test helper: install a Role summary keyed by `role_id`.

        `required_affordances` and `optional_affordances` accept any
        iterable of Affordance-value strings; the adapter freezes them
        into frozensets. Defaults are empty (matches the simplest
        smoke-test seed).
        """
        with self._lock:
            self._records[role_id] = RoleLookupResult(
                id=role_id,
                name=name,
                required_affordances=frozenset(required_affordances),
                optional_affordances=frozenset(optional_affordances),
            )

    async def lookup(self, role_id: UUID) -> RoleLookupResult | None:
        with self._lock:
            return self._records.get(role_id)


__all__ = ["InMemoryRoleLookup"]

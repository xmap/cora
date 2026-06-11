"""In-memory `FamilyLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` operation,
same None-on-missing semantics. A `threading.Lock` guards the dict
so concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresFamilyLookup` in `cora.equipment.adapters` is the
production option, reading `proj_equipment_family_summary`).
"""

from collections.abc import Iterable, Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.family_lookup import FamilyLookupResult


class InMemoryFamilyLookup:
    """Thread-safe in-memory implementation of the `FamilyLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, FamilyLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, FamilyLookupResult] = dict(seed) if seed is not None else {}
        self._lock = Lock()

    def register(
        self,
        family_id: UUID,
        name: str,
        status: str = "Defined",
        affordances: Iterable[str] = (),
        presents_as: Iterable[UUID] = (),
    ) -> None:
        """Test helper: install a Family summary keyed by `family_id`."""
        with self._lock:
            self._records[family_id] = FamilyLookupResult(
                id=family_id,
                name=name,
                status=status,
                affordances=frozenset(affordances),
                presents_as=frozenset(presents_as),
            )

    async def lookup(self, family_id: UUID) -> FamilyLookupResult | None:
        with self._lock:
            return self._records.get(family_id)


__all__ = ["InMemoryFamilyLookup"]

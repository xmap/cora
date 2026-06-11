"""In-memory `AssemblyLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` operation,
same None-on-missing semantics. A `threading.Lock` guards the dict
so concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresAssemblyLookup` in `cora.equipment.adapters` is the
production option, reading `proj_equipment_assembly_summary`).
"""

from collections.abc import Iterable, Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.assembly_lookup import AssemblyLookupResult


class InMemoryAssemblyLookup:
    """Thread-safe in-memory implementation of the `AssemblyLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, AssemblyLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, AssemblyLookupResult] = dict(seed) if seed is not None else {}
        self._lock = Lock()

    def register(
        self,
        assembly_id: UUID,
        name: str,
        status: str = "Defined",
        presents_as: Iterable[UUID] = (),
    ) -> None:
        """Test helper: install an Assembly summary keyed by `assembly_id`."""
        with self._lock:
            self._records[assembly_id] = AssemblyLookupResult(
                id=assembly_id,
                name=name,
                status=status,
                presents_as=frozenset(presents_as),
            )

    async def lookup(self, assembly_id: UUID) -> AssemblyLookupResult | None:
        with self._lock:
            return self._records.get(assembly_id)


__all__ = ["InMemoryAssemblyLookup"]

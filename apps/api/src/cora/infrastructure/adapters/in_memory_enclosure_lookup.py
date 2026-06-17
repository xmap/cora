"""In-memory `EnclosureLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` and
`find_by_ids` operations, same None-on-missing /
empty-list-on-no-match semantics, same Decommissioned-exclusion
posture on `find_by_ids`. A `threading.Lock` guards the dict so
concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresEnclosureLookup` in `cora.enclosure.adapters` is the
production option, reading `proj_enclosure_summary`).

Separate from the `AlwaysPermittedEnclosureLookup` inline stub on
the port: this adapter lets tests seed specific enclosure rows and
assert on the exact reference returned, whereas the stub
blanket-permits every id without holding state.
"""

from collections.abc import Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.enclosure_lookup import EnclosureLookupResult


class InMemoryEnclosureLookup:
    """Thread-safe in-memory implementation of the `EnclosureLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, EnclosureLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, EnclosureLookupResult] = dict(seed) if seed is not None else {}
        # facility_code is not on EnclosureLookupResult (the gate path
        # does not need it), so address resolution (lookup_by_name) keeps
        # it in a parallel map keyed by enclosure_id.
        self._facility_by_id: dict[UUID, str] = {}
        self._lock = Lock()

    def register(
        self,
        enclosure_id: UUID,
        name: str,
        permit_status: str = "Permitted",
        lifecycle: str = "Active",
        observed_at: str | None = None,
        source_kind: str | None = None,
        source_id: str | None = None,
        facility_code: str = "cora",
    ) -> None:
        """Test helper: install an enclosure reference keyed by `enclosure_id`.

        Default `permit_status="Permitted"` + `lifecycle="Active"`
        matches the most common happy-path shape consumers expect
        when seeding an active enclosure. Tests for non-permitted /
        tombstoned cases pass the matching strings explicitly.
        Observation fields default to `None` so callers only set them
        when the scenario under test cares about provenance.
        """
        with self._lock:
            self._records[enclosure_id] = EnclosureLookupResult(
                enclosure_id=enclosure_id,
                name=name,
                permit_status=permit_status,
                lifecycle=lifecycle,
                observed_at=observed_at,
                source_kind=source_kind,
                source_id=source_id,
            )
            self._facility_by_id[enclosure_id] = facility_code

    async def lookup(self, enclosure_id: UUID) -> EnclosureLookupResult | None:
        with self._lock:
            return self._records.get(enclosure_id)

    async def find_by_ids(self, *, enclosure_ids: frozenset[UUID]) -> list[EnclosureLookupResult]:
        if not enclosure_ids:
            return []
        with self._lock:
            return [
                reference
                for eid, reference in self._records.items()
                if eid in enclosure_ids and reference.lifecycle == "Active"
            ]

    async def lookup_by_name(
        self, *, facility_code: str, name: str
    ) -> EnclosureLookupResult | None:
        with self._lock:
            for eid, reference in self._records.items():
                if (
                    reference.name == name
                    and reference.lifecycle == "Active"
                    and self._facility_by_id.get(eid) == facility_code
                ):
                    return reference
        return None


__all__ = ["InMemoryEnclosureLookup"]

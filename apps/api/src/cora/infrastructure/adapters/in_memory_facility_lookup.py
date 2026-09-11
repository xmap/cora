"""In-memory `FacilityLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` + `lookup_by_code`
operations, same None-on-missing semantics. A `threading.Lock` guards
both the id-keyed dict and the code-keyed reverse index so concurrent
tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresFacilityLookup` in `cora.federation.adapters` is the
production option, reading `proj_federation_facility_summary`).
"""

from collections.abc import Mapping, Sequence
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.facility_lookup import FacilityLookupResult, FacilityStatusValue
from cora.shared.facility_code import FacilityCode


class InMemoryFacilityLookup:
    """Thread-safe in-memory implementation of the `FacilityLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, FacilityLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, FacilityLookupResult] = dict(seed) if seed is not None else {}
        self._by_code: dict[FacilityCode, UUID] = {
            record.code: facility_id for facility_id, record in self._records.items()
        }
        self._lock = Lock()

    def register(
        self,
        facility_id: UUID,
        code: str | FacilityCode,
        kind: str,
        status: FacilityStatusValue = "Active",
        trust_anchor_credential_ids: frozenset[UUID] = frozenset(),
    ) -> None:
        """Test helper: install a facility summary keyed by `facility_id`.

        `code` accepts either a raw `str` (constructed into a
        `FacilityCode` here) or a pre-built `FacilityCode` for callers
        that already hold the VO. Default `kind="Site"` matches the
        most common bootstrap shape; tests for Area cases pass `"Area"`
        explicitly. Default `status="Active"` matches the default
        register_facility ship state. Maintains the code-keyed reverse
        index so `lookup_by_code` resolves in O(1).
        """
        facility_code = code if isinstance(code, FacilityCode) else FacilityCode(code)
        with self._lock:
            self._records[facility_id] = FacilityLookupResult(
                id=facility_id,
                code=facility_code,
                kind=kind,
                status=status,
                trust_anchor_credential_ids=trust_anchor_credential_ids,
            )
            self._by_code[facility_code] = facility_id

    async def lookup(self, facility_id: UUID) -> FacilityLookupResult | None:
        with self._lock:
            return self._records.get(facility_id)

    async def lookup_by_code(self, code: FacilityCode) -> FacilityLookupResult | None:
        with self._lock:
            facility_id = self._by_code.get(code)
            if facility_id is None:
                return None
            return self._records.get(facility_id)

    async def list_active(self) -> Sequence[FacilityLookupResult]:
        with self._lock:
            return tuple(record for record in self._records.values() if record.status == "Active")


__all__ = ["InMemoryFacilityLookup"]

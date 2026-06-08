"""In-memory `FacilityLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` operation,
same None-on-missing semantics. A `threading.Lock` guards the dict
so concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresFacilityLookup` in `cora.federation.adapters` is the
production option, reading `proj_federation_facility_summary`).
"""

from collections.abc import Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode


class InMemoryFacilityLookup:
    """Thread-safe in-memory implementation of the `FacilityLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, FacilityLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, FacilityLookupResult] = dict(seed) if seed is not None else {}
        self._lock = Lock()

    def register(
        self,
        facility_id: UUID,
        code: str | FacilityCode,
        kind: str,
        status: str = "Active",
        trust_anchor_credential_ids: frozenset[UUID] = frozenset(),
    ) -> None:
        """Test helper: install a facility summary keyed by `facility_id`.

        `code` accepts either a raw `str` (constructed into a
        `FacilityCode` here) or a pre-built `FacilityCode` for callers
        that already hold the VO. Default `kind="Site"` matches the
        most common bootstrap shape; tests for Area cases pass `"Area"`
        explicitly. Default `status="Active"` matches the default
        register_facility ship state.
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

    async def lookup(self, facility_id: UUID) -> FacilityLookupResult | None:
        with self._lock:
            return self._records.get(facility_id)


__all__ = ["InMemoryFacilityLookup"]

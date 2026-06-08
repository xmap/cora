"""In-memory `CredentialLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` operation,
same None-on-missing semantics. A `threading.Lock` guards the dict
so concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresCredentialLookup` in `cora.federation.adapters` is the
production option, reading `proj_federation_credential_summary`).
"""

from collections.abc import Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.shared.facility_code import FacilityCode


class InMemoryCredentialLookup:
    """Thread-safe in-memory implementation of the `CredentialLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, CredentialLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, CredentialLookupResult] = dict(seed) if seed is not None else {}
        self._lock = Lock()

    def register(
        self,
        credential_id: UUID,
        facility_id: str | FacilityCode,
        purpose: str,
        status: str,
    ) -> None:
        """Test helper: install a credential summary keyed by `credential_id`.

        `facility_id` accepts either a raw `str` (constructed into a
        `FacilityCode` here) or a pre-built `FacilityCode` for callers
        that already hold the VO. Keeps the bulk of existing tests
        passing strings unchanged.
        """
        code = facility_id if isinstance(facility_id, FacilityCode) else FacilityCode(facility_id)
        with self._lock:
            self._records[credential_id] = CredentialLookupResult(
                id=credential_id,
                facility_id=code,
                purpose=purpose,
                status=status,
            )

    async def lookup(self, credential_id: UUID) -> CredentialLookupResult | None:
        with self._lock:
            return self._records.get(credential_id)


__all__ = ["InMemoryCredentialLookup"]

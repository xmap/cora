"""In-memory `ClearanceTemplateLookup` adapter for unit tests and the `test` app environment.

Mirrors the production adapter contract: same `lookup` operation,
same None-on-missing semantics. A `threading.Lock` guards the dict
so concurrent tasks see consistent state.

Not durable across process restarts and not safe for production
(`PostgresClearanceTemplateLookup` in `cora.safety.adapters` is the
production option, reading `proj_safety_clearance_template_summary`).
"""

from collections.abc import Mapping
from threading import Lock
from uuid import UUID

from cora.infrastructure.ports.clearance_template_lookup import ClearanceTemplateLookupResult


class InMemoryClearanceTemplateLookup:
    """Thread-safe in-memory implementation of the `ClearanceTemplateLookup` port."""

    def __init__(
        self,
        seed: Mapping[UUID, ClearanceTemplateLookupResult] | None = None,
    ) -> None:
        self._records: dict[UUID, ClearanceTemplateLookupResult] = (
            dict(seed) if seed is not None else {}
        )
        self._lock = Lock()

    def register(
        self,
        template_id: UUID,
        *,
        facility_code: str = "aps",
        code: str = "default-template",
        status: str = "Active",
        version: int = 1,
    ) -> None:
        """Test helper: install a clearance-template summary keyed by `template_id`.

        Defaults match the most common parent-chain scenario: an Active
        template in the pilot facility at version 1, which is the steady
        state for a freshly-activated template ready to be superseded
        by a new version.
        """
        with self._lock:
            self._records[template_id] = ClearanceTemplateLookupResult(
                id=template_id,
                facility_code=facility_code,
                code=code,
                status=status,
                version=version,
            )

    async def lookup(self, template_id: UUID) -> ClearanceTemplateLookupResult | None:
        with self._lock:
            return self._records.get(template_id)


__all__ = ["InMemoryClearanceTemplateLookup"]

"""Postgres adapter implementing `FacilityLookup` over `proj_federation_facility_summary`.

Consumed by Federation BC's `register_facility` handler via the
`Kernel.facility_lookup` port to validate `parent.kind=Site`
at registration time (per [[project-slice6-design]] L2; closes the
Slice 5 deferral). Future Sub-Slice B consumers
(`add_facility_trust_anchor_credential` decider) will also consume
this port. Reads the projection's primary-key row and returns `None`
when the facility id is unknown.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graca 2017,
Dudycz 2024): cross-aggregate integration at command time should go
through a replicated read model, NOT a synchronous replay of the
upstream aggregate. `proj_federation_facility_summary` is exactly
that: a denormalized cross-stream view maintained by the projection
worker. The lookup adapter reads it directly via the shared asyncpg
pool.

## Query shape

Two SELECTs, one per access method, both `LIMIT 1` and returning
`None` when no row matches. `lookup` keys by `facility_id` PK;
`lookup_by_code` keys by the cross-deployment convergent `code`
slug (enforced UNIQUE at the projection-table level so at most one
row matches, with `LIMIT 1` as a defensive belt). Facilities in
every status (`Active`, `Decommissioned`) are returned; consumer
deciders partition on `kind` or `status` (the `register_facility`
arm requires `kind == "Site"` for parents but accepts any status;
Slice 7+ cross-BC consumers may add status filters as their
domain semantics require).

## Enum coercion

`kind` and `status` are stored as `TEXT` columns. `kind` stays typed
`str` on the port's `FacilityLookupResult` (to keep
`cora.infrastructure.ports.facility_lookup` import-free of Federation
BC types); the adapter constructs `FacilityKind(row["kind"])` as a
validation step, and the validated `StrEnum` value IS-A `str`, so
the assignment into the `str`-typed field is exact. `status` is
typed as a `Literal` alias pinning `FacilityStatus`'s value set; the
adapter constructs `FacilityStatus(row["status"])` the same way, but
takes `.value` so the result narrows to exactly the alias, no cast
needed. Either way, a corrupted row whose `kind` or `status` is not
a known enum value surfaces as `ValueError` from the adapter rather
than as a silent wrong-value match downstream.

## JSONB array decoding

`trust_anchor_credential_ids` is stored as JSONB array of UUID
strings (per Slice 5 Sub-Slice B migration). The adapter materializes
the column as `frozenset[UUID]`. The port surface keeps the field
`frozenset[UUID]` (not `frozenset[CredentialId]`) to stay tach-clean;
Federation BC callers cast to `CredentialId` at the boundary.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
from collections.abc import Sequence
from typing import Any
from uuid import UUID

import asyncpg

from cora.federation.aggregates.facility.state import (
    FacilityKind,
    FacilityStatus,
)
from cora.infrastructure.ports.facility_lookup import FacilityLookupResult
from cora.shared.facility_code import FacilityCode

_LOOKUP_SQL = """
SELECT facility_id, code, kind, status, trust_anchor_credential_ids
FROM proj_federation_facility_summary
WHERE facility_id = $1
LIMIT 1
"""

_LOOKUP_BY_CODE_SQL = """
SELECT facility_id, code, kind, status, trust_anchor_credential_ids
FROM proj_federation_facility_summary
WHERE code = $1
LIMIT 1
"""

_LIST_ACTIVE_SQL = """
SELECT facility_id, code, kind, status, trust_anchor_credential_ids
FROM proj_federation_facility_summary
WHERE status = 'Active'
ORDER BY code
"""


class PostgresFacilityLookup:
    """asyncpg-backed `FacilityLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, facility_id: UUID) -> FacilityLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, facility_id)
        if row is None:
            return None
        return _row_to_result(row)

    async def lookup_by_code(self, code: FacilityCode) -> FacilityLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_BY_CODE_SQL, code.value)
        if row is None:
            return None
        return _row_to_result(row)

    async def list_active(self) -> Sequence[FacilityLookupResult]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_LIST_ACTIVE_SQL)
        return tuple(_row_to_result(row) for row in rows)


def _decode_trust_anchor_ids(raw: Any) -> frozenset[UUID]:
    """JSONB column comes back as str (asyncpg default) or list (jsonb-codec)."""
    if raw is None:
        return frozenset()
    if isinstance(raw, str):
        raw = json.loads(raw)
    return frozenset(UUID(str(v)) for v in raw)


def _row_to_result(row: Any) -> FacilityLookupResult:
    return FacilityLookupResult(
        id=row["facility_id"],
        code=FacilityCode(str(row["code"])),
        kind=FacilityKind(row["kind"]).value,
        status=FacilityStatus(row["status"]).value,
        trust_anchor_credential_ids=_decode_trust_anchor_ids(row["trust_anchor_credential_ids"]),
    )


__all__ = ["PostgresFacilityLookup"]

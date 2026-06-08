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

Single SELECT keyed by the `facility_id` primary key (LIMIT 1),
returning `None` when no row matches. Facilities in every status
(`Active`, `Decommissioned`) are returned; the
`register_facility` decider partitions on `kind == "Site"` (parent
must be Site tier) but does NOT filter on status (a Decommissioned
parent is structurally still a parent: the operator chose to keep
the lineage visible).

## Enum coercion

`kind` and `status` are stored as `TEXT` columns and are typed as
`str` on the port's `FacilityLookupResult` (to keep
`cora.infrastructure.ports.facility_lookup` import-free of Federation
BC types). The adapter still constructs `FacilityKind(row["kind"])` /
`FacilityStatus(row["status"])` as a validation step: a corrupted
row whose `kind` or `status` is not a known enum value surfaces as
`ValueError` from the adapter rather than as a silent wrong-kind
match downstream. The validated `StrEnum` value is `IS-A str`, so
the assignment into the dataclass's `str`-typed fields is exact.

## JSONB array decoding

`trust_anchor_credential_ids` is stored as JSONB array of UUID
strings (per Slice 5 Sub-Slice B migration). The adapter materializes
the column as `frozenset[UUID]`. The port surface keeps the field
`frozenset[UUID]` (not `frozenset[CredentialId]`) to stay tach-clean;
Federation BC callers cast to `CredentialId` at the boundary.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
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
        kind=FacilityKind(row["kind"]),
        status=FacilityStatus(row["status"]),
        trust_anchor_credential_ids=_decode_trust_anchor_ids(row["trust_anchor_credential_ids"]),
    )


__all__ = ["PostgresFacilityLookup"]

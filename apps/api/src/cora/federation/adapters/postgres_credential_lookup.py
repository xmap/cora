"""Postgres adapter implementing `CredentialLookup` over `proj_federation_credential_summary`.

Consumed by Federation BC's seal handlers (`initialize_seal`,
`rotate_seal_online_key`) via the `Kernel.credential_lookup` port
to validate cross-aggregate purpose binding and the status-Active
invariant before commit. Reads the projection's primary-key row and
returns `None` when the credential id is unknown.

## Why query the projection (not the event store)

Per modern DDD guidance (Khononov 2021, Herberto Graca 2017,
Dudycz 2024): cross-BC integration at command time should go through
a replicated read model, NOT a synchronous replay of the upstream
aggregate. `proj_federation_credential_summary` is exactly that:
a denormalized cross-stream view maintained by the projection
worker. The lookup adapter reads it directly via the shared
asyncpg pool.

## Query shape

Single SELECT keyed by the `credential_id` primary key (LIMIT 1),
returning `None` when no row matches. Credentials in every status
(`Active`, `Rotating`, `Revoked`) are returned; the Seal decider
partitions on `status == "Active"` so it can distinguish
"no credential at all" from "credential exists but Rotating/Revoked".

## Enum coercion

`purpose` and `status` are stored as `TEXT` columns and are
typed as `str` on the port's `CredentialLookupResult` (to keep
`cora.infrastructure.ports.credential_lookup` import-free of
Federation BC types). The adapter still constructs
`CredentialPurpose(row["purpose"])` / `CredentialStatus(row["status"])`
as a validation step: a corrupted row whose `purpose` or `status`
is not a known enum value surfaces as `ValueError` from the
adapter rather than as a silent wrong-purpose match downstream.
The validated `StrEnum` value is `IS-A str`, so the assignment
into the dataclass's `str`-typed fields is exact.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from typing import Any
from uuid import UUID

import asyncpg

from cora.federation.aggregates.credential.state import (
    CredentialPurpose,
    CredentialStatus,
)
from cora.infrastructure.ports.credential_lookup import CredentialLookupResult
from cora.shared.facility_code import FacilityCode

_LOOKUP_SQL = """
SELECT credential_id, facility_id, purpose, status
FROM proj_federation_credential_summary
WHERE credential_id = $1
LIMIT 1
"""


class PostgresCredentialLookup:
    """asyncpg-backed `CredentialLookup` implementation."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def lookup(self, credential_id: UUID) -> CredentialLookupResult | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(_LOOKUP_SQL, credential_id)
        if row is None:
            return None
        return _row_to_result(row)


def _row_to_result(row: Any) -> CredentialLookupResult:
    return CredentialLookupResult(
        id=row["credential_id"],
        facility_id=FacilityCode(str(row["facility_id"])),
        purpose=CredentialPurpose(row["purpose"]),
        status=CredentialStatus(row["status"]),
    )


__all__ = ["PostgresCredentialLookup"]

"""End-to-end PG integration test: `revoke_credential` cross-BC atomic write.

Pins the cross-BC, two-stream atomic-write contract under real
Postgres for a TERMINAL transition. `revoke_credential` writes BOTH a
`CredentialRevoked` event on the Credential stream AND a
`DecisionRegistered` audit event on the Decision stream in ONE
transaction via `EventStore.append_streams`.

Mirrors the `register_credential` cross-BC genesis precedent. Differs
in that the Credential stream's expected version on append is the
loaded version (1 after genesis), not zero; the Decision stream is
fresh (expected version zero). Cross-stream correlation lands in
`DecisionRegistered.choice = str(credential_id)`.

Seeds the target credential via the upstream `register_credential`
handler so the FSM walk Active -> Revoked is exercised end-to-end
against real Postgres (mirrors the test_clearance_fsm_walk_postgres
template recommended in the Credential design).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation.aggregates.credential import (
    CredentialPurpose,
    CredentialStatus,
    load_credential,
)
from cora.federation.features import register_credential, revoke_credential
from cora.federation.features.register_credential import RegisterCredential
from cora.federation.features.revoke_credential import RevokeCredential
from cora.federation.projections import CredentialSummaryProjection
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_REGISTERED_AT = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_REVOKED_AT = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed401")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed402")
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/signing#v1"
_PUBLIC_REF = "vault://kv/cora/federation/aps-2bm/signing/pub#v1"


def _register_command(audience: str) -> RegisterCredential:
    return RegisterCredential(
        facility_code="aps-2bm",
        audience=audience,
        purpose=CredentialPurpose.SIGNING,
        secret_ref=_SECRET_REF,
        public_material_ref=_PUBLIC_REF,
        expires_at=_EXPIRES_AT,
    )


async def _seed_active_credential(db_pool: asyncpg.Pool, audience: str) -> UUID:
    """Register a fresh Active credential against real Postgres and return its id."""
    seed_deps = build_postgres_deps(
        db_pool,
        now=_REGISTERED_AT,
        ids=[uuid4() for _ in range(5)],
    )
    return await register_credential.bind(seed_deps)(
        _register_command(audience),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_revoke_credential_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    suffix = uuid4().hex[:8]
    credential_id = await _seed_active_credential(db_pool, f"peer-{suffix}.example.org")

    revoke_deps = build_postgres_deps(
        db_pool,
        now=_REVOKED_AT,
        ids=[uuid4() for _ in range(5)],
    )
    await revoke_credential.bind(revoke_deps)(
        RevokeCredential(credential_id=credential_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    credential = await load_credential(revoke_deps.event_store, credential_id)
    assert credential is not None
    assert credential.id == credential_id
    assert credential.status is CredentialStatus.REVOKED


@pytest.mark.integration
async def test_revoke_credential_shared_xid8_across_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """The CredentialRevoked + DecisionRegistered audit events MUST land
    in the same Postgres transaction (shared xid8). The events table's
    `transaction_id xid8` column is populated by `pg_current_xact_id()`
    on insert; a successful `append_streams` inserts every event in one
    transaction, so the revoke's two emitted rows share the same xid.

    The genesis (registration) write happened in a SEPARATE transaction
    via `_seed_active_credential`, so we filter to the revoke-time pair
    only by joining on the audit's `choice` field (which carries
    str(credential_id))."""
    suffix = uuid4().hex[:8]
    credential_id = await _seed_active_credential(db_pool, f"peer-{suffix}.example.org")

    revoke_deps = build_postgres_deps(
        db_pool,
        now=_REVOKED_AT,
        ids=[uuid4() for _ in range(5)],
    )
    await revoke_credential.bind(revoke_deps)(
        RevokeCredential(credential_id=credential_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stream_type, transaction_id::text AS xid, event_type
              FROM events
             WHERE (
                       stream_type = 'Credential'
                   AND stream_id = $1
                   AND event_type = 'CredentialRevoked'
                   )
                OR (
                       stream_type = 'Decision'
                   AND payload->>'context' = 'CredentialRevoked'
                   AND payload->>'choice' = $2
                   )
             ORDER BY position
            """,
            credential_id,
            str(credential_id),
        )

    stream_types = {r["stream_type"] for r in rows}
    assert stream_types == {"Credential", "Decision"}, stream_types
    xids = {r["xid"] for r in rows}
    assert len(xids) == 1, f"expected shared xid8 across streams, got {xids}"


@pytest.mark.integration
async def test_revoke_credential_projection_lands_row(
    db_pool: asyncpg.Pool,
) -> None:
    """After draining projections, proj_federation_credential_summary should
    reflect status='Revoked' and revoked_at=_REVOKED_AT for the target row."""
    suffix = uuid4().hex[:8]
    audience = f"peer-{suffix}.example.org"
    credential_id = await _seed_active_credential(db_pool, audience)

    revoke_deps = build_postgres_deps(
        db_pool,
        now=_REVOKED_AT,
        ids=[uuid4() for _ in range(5)],
    )
    await revoke_credential.bind(revoke_deps)(
        RevokeCredential(credential_id=credential_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    registry.register(CredentialSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT credential_id, facility_id, audience, purpose,
                   status, registered_at, revoked_at
              FROM proj_federation_credential_summary
             WHERE credential_id = $1
            """,
            credential_id,
        )
    assert row is not None
    assert row["credential_id"] == credential_id
    assert row["facility_id"] == "aps-2bm"
    assert row["audience"] == audience
    assert row["purpose"] == CredentialPurpose.SIGNING.value
    assert row["status"] == CredentialStatus.REVOKED.value
    assert row["registered_at"] == _REGISTERED_AT
    assert row["revoked_at"] == _REVOKED_AT

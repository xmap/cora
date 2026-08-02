"""End-to-end PG integration test: `register_credential` cross-BC atomic write.

Pins the cross-BC, two-stream atomic-write contract under real
Postgres. `register_credential` writes BOTH a `CredentialRegistered`
event on the Credential stream AND a `DecisionRegistered` audit
event on the Decision stream in ONE transaction via
`EventStore.append_streams`.

Mirrors the `define_permit` cross-BC precedent (`PermitDefined` +
`DecisionRegistered`). Cross-stream correlation lands in
`DecisionRegistered.choice = str(credential_id)`.
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
from cora.federation.features import register_credential
from cora.federation.features.register_credential import RegisterCredential
from cora.federation.projections import CredentialSummaryProjection
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed301")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed302")
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/signing#v1"
_PUBLIC_REF = "vault://kv/cora/federation/aps-2bm/signing/pub#v1"


def _command(
    *,
    facility_code: str = "aps-2bm",
    audience: str = "peer.example.org",
    purpose: CredentialPurpose = CredentialPurpose.SIGNING,
    secret_ref: str = _SECRET_REF,
) -> RegisterCredential:
    return RegisterCredential(
        facility_code=facility_code,
        audience=audience,
        purpose=purpose,
        secret_ref=secret_ref,
        public_material_ref=_PUBLIC_REF,
        expires_at=_EXPIRES_AT,
    )


@pytest.mark.integration
async def test_register_credential_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])

    # Unique identity-tuple per test to avoid the projection's
    # (facility_id, audience, purpose) UNIQUE collision across runs
    # sharing the same db_pool.
    suffix = uuid4().hex[:8]
    credential_id = await register_credential.bind(deps)(
        _command(audience=f"peer-{suffix}.example.org"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Credential stream populated; status reaches Active via the genesis event.
    credential = await load_credential(deps.event_store, credential_id)
    assert credential is not None
    assert credential.id == credential_id
    assert credential.status is CredentialStatus.ACTIVE
    assert credential.facility_code.value == "aps-2bm"
    assert credential.audience == f"peer-{suffix}.example.org"
    assert credential.purpose is CredentialPurpose.SIGNING
    assert credential.secret_ref == _SECRET_REF
    assert credential.public_material_ref == _PUBLIC_REF
    assert credential.expires_at == _EXPIRES_AT
    assert credential.registered_by == _PRINCIPAL_ID
    assert credential.rotation_pending_secret_ref is None
    assert credential.rotation_pending_public_material_ref is None


@pytest.mark.integration
async def test_register_credential_shared_xid8_across_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """Both events MUST land in the same Postgres transaction (shared xid8).

    The events table has a `transaction_id xid8` column populated by
    `pg_current_xact_id()` on insert. Successful `append_streams`
    inserts every event in one transaction, so the Credential +
    Decision rows share the same `transaction_id`.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])

    suffix = uuid4().hex[:8]
    credential_id = await register_credential.bind(deps)(
        _command(audience=f"peer-{suffix}.example.org"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stream_type, transaction_id::text AS xid, payload
              FROM events
             WHERE (stream_type = 'Credential' AND stream_id = $1)
                OR (stream_type = 'Decision' AND payload->>'choice' = $2)
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
async def test_register_credential_projection_lands_row(
    db_pool: asyncpg.Pool,
) -> None:
    """After draining projections, proj_federation_credential_summary should
    carry the new row with status='Active' and the genesis fields."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])

    suffix = uuid4().hex[:8]
    audience = f"peer-{suffix}.example.org"
    credential_id = await register_credential.bind(deps)(
        _command(audience=audience),
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
                   secret_ref, public_material_ref, expires_at,
                   status, rotation_pending_secret_ref,
                   rotation_pending_public_material_ref,
                   registered_at, rotation_started_at, revoked_at
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
    assert row["secret_ref"] == _SECRET_REF
    assert row["public_material_ref"] == _PUBLIC_REF
    assert row["expires_at"] == _EXPIRES_AT
    assert row["status"] == CredentialStatus.ACTIVE.value
    assert row["rotation_pending_secret_ref"] is None
    assert row["rotation_pending_public_material_ref"] is None
    assert row["registered_at"] == _NOW
    assert row["rotation_started_at"] is None
    assert row["revoked_at"] is None

"""Integration tests for `PostgresCredentialLookup` against a real Postgres.

Pins the cross-stream query contract under the real Federation
projection: seeds credentials via `register_credential` (and the
rotation / revocation handlers), drains the projection worker, then
queries through the adapter and verifies the result matches the
seeded credentials. None-on-missing semantics are pinned via an
unseeded id.

Mirrors `tests/integration/test_postgres_clearance_lookup.py` and
`tests/integration/test_postgres_supply_lookup.py`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation._projections import register_federation_projections
from cora.federation.adapters import PostgresCredentialLookup
from cora.federation.aggregates.credential import (
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.features import (
    register_credential,
    revoke_credential,
    start_credential_rotation,
)
from cora.federation.features.register_credential import RegisterCredential
from cora.federation.features.revoke_credential import RevokeCredential
from cora.federation.features.start_credential_rotation import StartCredentialRotation
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.facility_code import FacilityCode
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 5, 31, 13, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 31, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fcd001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fcd002")
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/seal-online#v1"
_NEW_SECRET_REF = "vault://kv/cora/federation/aps-2bm/seal-online#v2"


async def _drain_federation(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_federation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


async def _seed_active_credential(
    db_pool: asyncpg.Pool,
    *,
    facility_code: str,
    audience: str,
    purpose: CredentialPurpose,
    secret_ref: str = _SECRET_REF,
) -> UUID:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    return await register_credential.bind(deps)(
        RegisterCredential(
            facility_code=facility_code,
            audience=audience,
            purpose=purpose,
            secret_ref=secret_ref,
            public_material_ref=None,
            expires_at=_EXPIRES_AT,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )


@pytest.mark.integration
async def test_lookup_returns_all_four_fields_for_active_credential(
    db_pool: asyncpg.Pool,
) -> None:
    suffix = uuid4().hex[:8]
    cid = await _seed_active_credential(
        db_pool,
        facility_code="aps-2bm",
        audience=f"peer-{suffix}.example.org",
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING,
    )
    await _drain_federation(db_pool)

    lookup = PostgresCredentialLookup(db_pool)
    result = await lookup.lookup(cid)

    assert result is not None
    assert result.id == cid
    assert result.facility_id == FacilityCode("aps-2bm")
    assert result.purpose == CredentialPurpose.SEAL_ONLINE_SIGNING.value
    assert result.status == CredentialStatus.ACTIVE.value


@pytest.mark.integration
async def test_lookup_unknown_id_returns_none(db_pool: asyncpg.Pool) -> None:
    """Adapter contract: missing rows return None, not raise."""
    lookup = PostgresCredentialLookup(db_pool)
    result = await lookup.lookup(uuid4())
    assert result is None


@pytest.mark.integration
async def test_lookup_returns_rotating_status(db_pool: asyncpg.Pool) -> None:
    """Credentials mid-rotation are returned with status='Rotating';
    the Seal decider partitions on Active-only so it can distinguish
    "no credential at all" from "credential exists but Rotating"."""
    suffix = uuid4().hex[:8]
    cid = await _seed_active_credential(
        db_pool,
        facility_code="aps-2bm",
        audience=f"peer-{suffix}.example.org",
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING,
    )
    deps = build_postgres_deps(db_pool, now=_LATER, ids=[uuid4() for _ in range(3)])
    await start_credential_rotation.bind(deps)(
        StartCredentialRotation(
            credential_id=cid,
            new_secret_ref=_NEW_SECRET_REF,
            new_public_material_ref=None,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_federation(db_pool)

    lookup = PostgresCredentialLookup(db_pool)
    result = await lookup.lookup(cid)

    assert result is not None
    assert result.id == cid
    assert result.status == CredentialStatus.ROTATING.value
    assert result.purpose == CredentialPurpose.SEAL_ONLINE_SIGNING.value


@pytest.mark.integration
async def test_lookup_returns_revoked_status(db_pool: asyncpg.Pool) -> None:
    """Revoked credentials are still returned; the Seal decider
    rejects them on the status check, not on absence."""
    suffix = uuid4().hex[:8]
    cid = await _seed_active_credential(
        db_pool,
        facility_code="aps-2bm",
        audience=f"peer-{suffix}.example.org",
        purpose=CredentialPurpose.SEAL_OFFLINE_ROOT,
    )
    deps = build_postgres_deps(db_pool, now=_LATER, ids=[uuid4() for _ in range(3)])
    await revoke_credential.bind(deps)(
        RevokeCredential(credential_id=cid, reason="operator decommission"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_federation(db_pool)

    lookup = PostgresCredentialLookup(db_pool)
    result = await lookup.lookup(cid)

    assert result is not None
    assert result.id == cid
    assert result.status == CredentialStatus.REVOKED.value
    assert result.purpose == CredentialPurpose.SEAL_OFFLINE_ROOT.value


@pytest.mark.integration
async def test_lookup_isolates_records_by_id(db_pool: asyncpg.Pool) -> None:
    """Two distinct credentials in the same projection: looking up
    one MUST return only that one's fields."""
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]
    cid_online = await _seed_active_credential(
        db_pool,
        facility_code="aps-2bm",
        audience=f"peer-a-{suffix_a}.example.org",
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING,
    )
    cid_offline = await _seed_active_credential(
        db_pool,
        facility_code="aps-2bm",
        audience=f"peer-b-{suffix_b}.example.org",
        purpose=CredentialPurpose.SEAL_OFFLINE_ROOT,
    )
    await _drain_federation(db_pool)

    lookup = PostgresCredentialLookup(db_pool)
    online = await lookup.lookup(cid_online)
    offline = await lookup.lookup(cid_offline)

    assert online is not None
    assert online.id == cid_online
    assert online.purpose == CredentialPurpose.SEAL_ONLINE_SIGNING.value

    assert offline is not None
    assert offline.id == cid_offline
    assert offline.purpose == CredentialPurpose.SEAL_OFFLINE_ROOT.value

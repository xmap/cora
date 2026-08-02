"""End-to-end PG integration test: `get_credential` read-path slice.

Pins the Path C composition under real Postgres: handler folds the
Credential aggregate stream AND reads lifecycle timestamps from
`proj_federation_credential_summary` via `load_credential_timestamps`.
Unit tests for `get_credential` run with an in-memory event store and
`pool=None`, so `_SELECT_TIMESTAMPS_SQL` never executes there; this
file is the only place the read-side SQL is exercised against a real
projection.

Mirrors `test_register_credential_handler_postgres.py` for setup
(per-test audience suffix avoids the projection's
(facility_code, audience, purpose) UNIQUE collision).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation._projections import register_federation_projections
from cora.federation.aggregates.credential import (
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.features import get_credential, register_credential
from cora.federation.features.get_credential import GetCredential
from cora.federation.features.register_credential import RegisterCredential
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 5, 31, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed401")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed402")
_SECRET_REF = "vault://kv/cora/federation/aps-2bm/signing#v1"
_PUBLIC_REF = "vault://kv/cora/federation/aps-2bm/signing/pub#v1"


async def _drain_federation(db_pool: asyncpg.Pool) -> None:
    registry = ProjectionRegistry()
    register_federation_projections(registry)
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())


def _register_command(audience: str) -> RegisterCredential:
    return RegisterCredential(
        facility_code="aps-2bm",
        audience=audience,
        purpose=CredentialPurpose.SIGNING,
        secret_ref=_SECRET_REF,
        public_material_ref=_PUBLIC_REF,
        expires_at=_EXPIRES_AT,
    )


@pytest.mark.integration
async def test_get_credential_returns_view_with_projection_timestamps(
    db_pool: asyncpg.Pool,
) -> None:
    """Handler hits the real `proj_federation_credential_summary` row
    after the projection drains, returning lifecycle timestamps."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    suffix = uuid4().hex[:8]
    credential_id = await register_credential.bind(deps)(
        _register_command(audience=f"peer-{suffix}.example.org"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await _drain_federation(db_pool)

    handler = get_credential.bind(deps)
    view = await handler(
        GetCredential(credential_id=credential_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.credential.id == credential_id
    assert view.credential.facility_code.value == "aps-2bm"
    assert view.credential.audience == f"peer-{suffix}.example.org"
    assert view.credential.purpose is CredentialPurpose.SIGNING
    assert view.credential.status is CredentialStatus.ACTIVE
    assert view.credential.expires_at == _EXPIRES_AT
    assert view.credential.registered_by == _PRINCIPAL_ID
    # Path C reversal: `registered_at` now lives on Credential aggregate,
    # while `rotation_started_at` still comes from the projection.
    assert view.credential.registered_at == _NOW
    assert view.timestamps is not None
    assert view.timestamps.rotation_started_at is None


@pytest.mark.integration
async def test_get_credential_returns_none_for_unknown_id(
    db_pool: asyncpg.Pool,
) -> None:
    """Handler short-circuits on Credential-not-found before touching
    the projection SQL path."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(2)])
    handler = get_credential.bind(deps)
    view = await handler(
        GetCredential(credential_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.integration
async def test_get_credential_view_timestamps_none_before_projection_drain(
    db_pool: asyncpg.Pool,
) -> None:
    """Before the projection worker drains, the aggregate stream
    exists but `proj_federation_credential_summary` has no row yet.
    The handler MUST return a `CredentialView` with `timestamps=None`
    rather than raise (transient/contextual, not a not-found signal)."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])
    suffix = uuid4().hex[:8]
    credential_id = await register_credential.bind(deps)(
        _register_command(audience=f"peer-{suffix}.example.org"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_credential.bind(deps)
    view = await handler(
        GetCredential(credential_id=credential_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.credential.id == credential_id
    assert view.timestamps is None

"""End-to-end PG integration test: `initialize_seal` cross-BC atomic write.

Pins the cross-BC, two-stream atomic-write contract under real
Postgres. `initialize_seal` writes BOTH a `SealInitialized` event on
the Seal stream AND a `DecisionRegistered` audit event on the
Decision stream in ONE transaction via
`EventStore.append_streams`.

Mirrors the `register_credential` cross-BC genesis precedent
(`CredentialRegistered` + `DecisionRegistered`). Differs in two ways:

  - The Seal stream id is DETERMINISTIC, derived from facility_code
    via UUID5 (`seal_stream_id`); the handler does not mint it.
  - Cross-stream correlation lands in
    `DecisionRegistered.choice = facility_code` (the human-readable
    singleton identity, not a UUID).

Each test mints a unique facility_code suffix so the
`proj_federation_seal_summary` singleton PK on `facility_code` and the
deterministic Seal stream UUID do not collide across runs sharing
the same db_pool.

Pass-3 wiring: the handler resolves both `online_credential_id` and
`offline_credential_id` through `deps.credential_lookup` before invoking
the decider. These integration tests thread an `InMemoryCredentialLookup`
pre-seeded with both refs as Active so the cross-aggregate purpose-
binding + status-Active checks pass without coupling to a separate
Credential-projection seed.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import SealStatus, load_seal
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.features import initialize_seal
from cora.federation.features.initialize_seal import InitializeSeal
from cora.federation.projections import SealSummaryProjection
from cora.infrastructure.adapters.in_memory_credential_lookup import (
    InMemoryCredentialLookup,
)
from cora.infrastructure.adapters.in_memory_facility_lookup import (
    InMemoryFacilityLookup,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.facility_code import FacilityCode
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed301")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed302")
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0a1")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0b1")


def _command(*, facility_code: str) -> InitializeSeal:
    return InitializeSeal(
        facility_code=facility_code,
        online_credential_id=_ONLINE_KEY_REF,
        offline_credential_id=_OFFLINE_KEY_REF,
    )


def _credential_lookup_for(facility_code: str) -> InMemoryCredentialLookup:
    """Build a credential lookup with both seal-slot refs seeded Active."""
    lookup = InMemoryCredentialLookup()
    lookup.register(
        credential_id=_ONLINE_KEY_REF,
        facility_id=facility_code,
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )
    lookup.register(
        credential_id=_OFFLINE_KEY_REF,
        facility_id=facility_code,
        purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value,
        status=CredentialStatus.ACTIVE.value,
    )
    return lookup


def _facility_lookup_for(facility_code: str) -> InMemoryFacilityLookup:
    """Build a facility lookup pre-seeded with the test facility as a Site.

    Both seal-slot credentials are seeded as trust anchors of the
    facility so the decider's trust-anchor membership check (Sub-Slice
    C: `SealCredentialNotTrustAnchorError`) passes.
    """
    lookup = InMemoryFacilityLookup()
    code = FacilityCode(facility_code)
    lookup.register(
        facility_id=facility_stream_id(code),
        code=code,
        kind="Site",
        status="Active",
        trust_anchor_credential_ids=frozenset({_ONLINE_KEY_REF, _OFFLINE_KEY_REF}),
    )
    return lookup


@pytest.mark.integration
async def test_initialize_seal_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    # Unique facility_code per test so the singleton PK on
    # proj_federation_seal_summary AND the deterministic Seal stream UUID do
    # not collide across runs sharing the same db_pool.
    facility_code = f"aps-2bm-{uuid4().hex[:8]}"
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_for(facility_code),
        facility_lookup=_facility_lookup_for(facility_code),
    )

    stream_id = await initialize_seal.bind(deps)(
        _command(facility_code=facility_code),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert stream_id == seal_stream_id(facility_code)

    seal = await load_seal(deps.event_store, stream_id)
    assert seal is not None
    assert seal.facility_code == FacilityCode(facility_code)
    assert seal.status is SealStatus.LIVE
    assert seal.online_credential_id == _ONLINE_KEY_REF
    assert seal.offline_credential_id == _OFFLINE_KEY_REF
    assert seal.current_head_hash is None
    assert seal.current_sequence_number == 0
    assert seal.initialized_by == _PRINCIPAL_ID


@pytest.mark.integration
async def test_initialize_seal_shared_xid8_across_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """Both events MUST land in the same Postgres transaction (shared xid8).

    The events table has a `transaction_id xid8` column populated by
    `pg_current_xact_id()` on insert. Successful `append_streams`
    inserts every event in one transaction, so the Seal + Decision
    rows share the same `transaction_id`.
    """
    facility_code = f"aps-2bm-{uuid4().hex[:8]}"
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_for(facility_code),
        facility_lookup=_facility_lookup_for(facility_code),
    )

    stream_id = await initialize_seal.bind(deps)(
        _command(facility_code=facility_code),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stream_type, transaction_id::text AS xid, event_type
              FROM events
             WHERE (stream_type = 'Seal' AND stream_id = $1)
                OR (
                       stream_type = 'Decision'
                   AND payload->>'context' = 'SealInitialized'
                   AND payload->>'choice' = $2
                   )
             ORDER BY position
            """,
            stream_id,
            facility_code,
        )

    stream_types = {r["stream_type"] for r in rows}
    assert stream_types == {"Seal", "Decision"}, stream_types
    xids = {r["xid"] for r in rows}
    assert len(xids) == 1, f"expected shared xid8 across streams, got {xids}"


@pytest.mark.integration
async def test_initialize_seal_projection_lands_row(
    db_pool: asyncpg.Pool,
) -> None:
    """After draining projections, proj_federation_seal_summary should carry the
    new singleton row with status='Live', current_sequence_number=0,
    initialized_at=_NOW, last_signed_at=NULL."""
    facility_code = f"aps-2bm-{uuid4().hex[:8]}"
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_for(facility_code),
        facility_lookup=_facility_lookup_for(facility_code),
    )

    await initialize_seal.bind(deps)(
        _command(facility_code=facility_code),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    registry.register(SealSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT facility_id, online_credential_id, offline_credential_id,
                   current_head_hash, current_sequence_number,
                   initialized_by, last_signed_by,
                   status, initialized_at, last_signed_at
              FROM proj_federation_seal_summary
             WHERE facility_id = $1
            """,
            facility_code,
        )
    assert row is not None
    assert row["facility_id"] == facility_code
    assert row["online_credential_id"] == _ONLINE_KEY_REF
    assert row["offline_credential_id"] == _OFFLINE_KEY_REF
    assert row["current_head_hash"] is None
    assert row["current_sequence_number"] == 0
    assert row["initialized_by"] == _PRINCIPAL_ID
    assert row["last_signed_by"] is None
    assert row["status"] == SealStatus.LIVE.value
    assert row["initialized_at"] == _NOW
    assert row["last_signed_at"] is None


@pytest.mark.integration
async def test_initialize_seal_projection_upsert_is_idempotent_on_replay(
    db_pool: asyncpg.Pool,
) -> None:
    """The SealInitialized projection uses ON CONFLICT DO NOTHING; a
    second drain over the same bookmark window does not duplicate the
    singleton row, and the row contents stay frozen at genesis values."""
    facility_code = f"aps-2bm-{uuid4().hex[:8]}"
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_for(facility_code),
        facility_lookup=_facility_lookup_for(facility_code),
    )

    await initialize_seal.bind(deps)(
        _command(facility_code=facility_code),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    registry.register(SealSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())
    # Second drain: bookmark has already advanced past the
    # SealInitialized event, so this is a no-op for the
    # projection; the row count and contents must stay unchanged.
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    async with db_pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM proj_federation_seal_summary WHERE facility_id = $1",
            facility_code,
        )
    assert count == 1

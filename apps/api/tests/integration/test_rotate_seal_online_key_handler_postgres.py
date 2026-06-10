"""End-to-end PG integration test: `rotate_seal_online_key` cross-BC atomic write.

Pins the cross-BC, two-stream atomic-write contract under real
Postgres for a mid-lifecycle Live -> Live transition.
`rotate_seal_online_key` writes BOTH a `SealOnlineKeyRotated` event on
the Seal stream AND a `DecisionRegistered` audit event on the Decision
stream in ONE transaction via `EventStore.append_streams`.

Mirrors the `revoke_credential` cross-BC mid-lifecycle precedent.
Differs in that the Seal stream's expected version on append is the
loaded version (1 after genesis), not zero; the Decision stream is
fresh (expected version zero). Cross-stream correlation lands in
`DecisionRegistered.choice = facility_id` (the singleton's domain id).

Seeds the target Seal via the upstream `initialize_seal` handler so
the FSM walk Live -> Live (with online ref swapped) is exercised
end-to-end against real Postgres.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation.aggregates.credential import (
    CredentialPurpose,
    CredentialStatus,
)
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import (
    SealStatus,
    load_seal,
)
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.features import initialize_seal, rotate_seal_online_key
from cora.federation.features.initialize_seal import InitializeSeal
from cora.federation.features.rotate_seal_online_key import RotateSealOnlineKey
from cora.federation.projections import SealSummaryProjection
from cora.infrastructure.adapters.in_memory_credential_lookup import (
    InMemoryCredentialLookup,
)
from cora.infrastructure.adapters.in_memory_facility_lookup import (
    InMemoryFacilityLookup,
)
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from cora.shared.facility_code import FacilityCode
from tests.integration._helpers import build_postgres_deps

_INITIALIZED_AT = datetime(2026, 5, 30, 10, 0, 0, tzinfo=UTC)
_ROTATED_AT = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed401")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed402")


def _build_facility_lookup_for(
    facility_code: str,
    *,
    trust_anchors: frozenset[UUID] = frozenset(),
) -> InMemoryFacilityLookup:
    """Seed an `InMemoryFacilityLookup` for the test's self-Facility.

    `trust_anchors` must include the credential IDs the seal handler
    will validate via Slice 6 Sub-Slice C's structural set-membership
    check; otherwise `SealCredentialNotTrustAnchorError` fires before
    `FacilityNotFoundError` is even reached.
    """
    lookup = InMemoryFacilityLookup()
    lookup.register(
        facility_id=facility_stream_id(FacilityCode(facility_code)),
        code=facility_code,
        kind="Site",
        trust_anchor_credential_ids=trust_anchors,
    )
    return lookup


async def _seed_live_seal(db_pool: asyncpg.Pool, facility_id: str) -> tuple[UUID, UUID, UUID]:
    """Initialize a fresh Live Seal against real Postgres.

    Returns `(stream_id, online_credential_id, offline_credential_id)` so the test
    can assert the post-rotation state against the seeded refs. The
    handler's Pass-3 credential-lookup gate is satisfied by threading
    an `InMemoryCredentialLookup` pre-seeded with both refs Active.
    The Slice 6 Sub-Slice C trust-anchor check is satisfied by seeding
    both credential refs into the Facility's trust_anchor_credential_ids.
    """
    online_credential_id = uuid4()
    offline_credential_id = uuid4()
    seed_lookup = InMemoryCredentialLookup()
    seed_lookup.register(
        credential_id=online_credential_id,
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )
    seed_lookup.register(
        credential_id=offline_credential_id,
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_OFFLINE_ROOT.value,
        status=CredentialStatus.ACTIVE.value,
    )
    seed_deps = build_postgres_deps(
        db_pool,
        now=_INITIALIZED_AT,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=seed_lookup,
        facility_lookup=_build_facility_lookup_for(
            facility_id,
            trust_anchors=frozenset({online_credential_id, offline_credential_id}),
        ),
    )
    stream_id = await initialize_seal.bind(seed_deps)(
        InitializeSeal(
            facility_code=facility_id,
            online_credential_id=online_credential_id,
            offline_credential_id=offline_credential_id,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    return stream_id, online_credential_id, offline_credential_id


def _credential_lookup_with(
    new_online_credential_id: UUID,
    facility_id: str,
) -> InMemoryCredentialLookup:
    """Build a credential lookup with `new_online_credential_id` seeded Active.

    The integration tests don't depend on a real `PostgresCredentialLookup`
    today: the production adapter would query
    `proj_federation_credential_summary`, which is not seeded here.
    Threading an `InMemoryCredentialLookup` keeps the cross-aggregate
    purpose-binding check exercised end-to-end without coupling these
    Seal tests to a separate Credential-projection setup.
    """
    lookup = InMemoryCredentialLookup()
    lookup.register(
        credential_id=new_online_credential_id,
        facility_id=facility_id,
        purpose=CredentialPurpose.SEAL_ONLINE_SIGNING.value,
        status=CredentialStatus.ACTIVE.value,
    )
    return lookup


@pytest.mark.integration
async def test_rotate_seal_online_key_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    suffix = uuid4().hex[:8]
    facility_id = f"aps-2bm-{suffix}"
    stream_id, _, offline_credential_id = await _seed_live_seal(db_pool, facility_id)
    new_online_credential_id = uuid4()

    rotate_deps = build_postgres_deps(
        db_pool,
        now=_ROTATED_AT,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_with(new_online_credential_id, facility_id),
        facility_lookup=_build_facility_lookup_for(
            facility_id,
            trust_anchors=frozenset({new_online_credential_id, offline_credential_id}),
        ),
    )
    await rotate_seal_online_key.bind(rotate_deps)(
        RotateSealOnlineKey(
            facility_code=facility_id,
            new_online_credential_id=new_online_credential_id,
            signed_by_offline_root=True,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    seal = await load_seal(rotate_deps.event_store, stream_id)
    assert seal is not None
    assert seal.facility_code.value == facility_id
    assert seal.status is SealStatus.LIVE
    assert seal.online_credential_id == new_online_credential_id
    assert seal.offline_credential_id == offline_credential_id
    assert seal.online_credential_id != seal.offline_credential_id
    # Key fields not touched by rotation stay unchanged.
    assert seal.current_head_hash is None
    assert seal.current_sequence_number == 0


@pytest.mark.integration
async def test_rotate_seal_online_key_shared_xid8_across_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """The SealOnlineKeyRotated + DecisionRegistered audit events MUST
    land in the same Postgres transaction (shared xid8). The events
    table's `transaction_id xid8` column is populated by
    `pg_current_xact_id()` on insert; a successful `append_streams`
    inserts every event in one transaction, so the rotate's two emitted
    rows share the same xid.

    The genesis (initialization) write happened in a SEPARATE transaction
    via `_seed_live_seal`, so we filter to the rotate-time pair only by
    joining on the audit's `context` field
    (`context = 'SealOnlineKeyRotated'`)."""
    suffix = uuid4().hex[:8]
    facility_id = f"aps-2bm-{suffix}"
    stream_id, _, offline_credential_id = await _seed_live_seal(db_pool, facility_id)
    new_online_credential_id = uuid4()

    rotate_deps = build_postgres_deps(
        db_pool,
        now=_ROTATED_AT,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_with(new_online_credential_id, facility_id),
        facility_lookup=_build_facility_lookup_for(
            facility_id,
            trust_anchors=frozenset({new_online_credential_id, offline_credential_id}),
        ),
    )
    await rotate_seal_online_key.bind(rotate_deps)(
        RotateSealOnlineKey(
            facility_code=facility_id,
            new_online_credential_id=new_online_credential_id,
            signed_by_offline_root=True,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stream_type, transaction_id::text AS xid, event_type
              FROM events
             WHERE (
                       stream_type = 'Seal'
                   AND stream_id = $1
                   AND event_type = 'SealOnlineKeyRotated'
                   )
                OR (
                       stream_type = 'Decision'
                   AND payload->>'context' = 'SealOnlineKeyRotated'
                   AND payload->>'choice' = $2
                   )
             ORDER BY position
            """,
            stream_id,
            facility_id,
        )

    stream_types = {r["stream_type"] for r in rows}
    assert stream_types == {"Seal", "Decision"}, stream_types
    xids = {r["xid"] for r in rows}
    assert len(xids) == 1, f"expected shared xid8 across streams, got {xids}"


@pytest.mark.integration
async def test_rotate_seal_online_key_projection_lands_new_online_ref(
    db_pool: asyncpg.Pool,
) -> None:
    """After draining projections, proj_federation_seal_summary should reflect the
    rotated `online_credential_id` while leaving `offline_credential_id` and `status`
    unchanged."""
    suffix = uuid4().hex[:8]
    facility_id = f"aps-2bm-{suffix}"
    _, _, offline_credential_id = await _seed_live_seal(db_pool, facility_id)
    new_online_credential_id = uuid4()

    rotate_deps = build_postgres_deps(
        db_pool,
        now=_ROTATED_AT,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_with(new_online_credential_id, facility_id),
        facility_lookup=_build_facility_lookup_for(
            facility_id,
            trust_anchors=frozenset({new_online_credential_id, offline_credential_id}),
        ),
    )
    await rotate_seal_online_key.bind(rotate_deps)(
        RotateSealOnlineKey(
            facility_code=facility_id,
            new_online_credential_id=new_online_credential_id,
            signed_by_offline_root=True,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    registry.register(SealSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT facility_id, online_credential_id, offline_credential_id,
                   status, current_head_hash, current_sequence_number,
                   initialized_at
              FROM proj_federation_seal_summary
             WHERE facility_id = $1
            """,
            facility_id,
        )
    assert row is not None
    assert row["facility_id"] == facility_id
    assert row["online_credential_id"] == new_online_credential_id
    assert row["offline_credential_id"] == offline_credential_id
    assert row["online_credential_id"] != row["offline_credential_id"]
    assert row["status"] == SealStatus.LIVE.value
    assert row["current_head_hash"] is None
    assert row["current_sequence_number"] == 0
    assert row["initialized_at"] == _INITIALIZED_AT


@pytest.mark.integration
async def test_rotate_seal_online_key_targets_deterministic_stream_id(
    db_pool: asyncpg.Pool,
) -> None:
    """The handler derives the Seal stream id via UUID5 from facility_id;
    the rotate event MUST land on the same deterministic stream the
    genesis went to."""
    suffix = uuid4().hex[:8]
    facility_id = f"aps-2bm-{suffix}"
    seeded_stream_id, _, offline_credential_id = await _seed_live_seal(db_pool, facility_id)
    expected_stream_id = seal_stream_id(facility_id)
    assert seeded_stream_id == expected_stream_id

    new_online_credential_id = uuid4()
    rotate_deps = build_postgres_deps(
        db_pool,
        now=_ROTATED_AT,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_with(new_online_credential_id, facility_id),
        facility_lookup=_build_facility_lookup_for(
            facility_id,
            trust_anchors=frozenset({new_online_credential_id, offline_credential_id}),
        ),
    )
    await rotate_seal_online_key.bind(rotate_deps)(
        RotateSealOnlineKey(
            facility_code=facility_id,
            new_online_credential_id=new_online_credential_id,
            signed_by_offline_root=True,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_type,
                   payload->>'new_online_credential_id' AS new_ref,
                   (payload->>'signed_by_offline_root')::bool AS signed_root
              FROM events
             WHERE stream_type = 'Seal'
               AND stream_id = $1
               AND event_type = 'SealOnlineKeyRotated'
            """,
            expected_stream_id,
        )
    assert len(rows) == 1
    assert rows[0]["new_ref"] == str(new_online_credential_id)
    assert rows[0]["signed_root"] is True

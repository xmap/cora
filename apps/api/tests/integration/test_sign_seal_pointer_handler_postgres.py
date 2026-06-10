"""End-to-end PG integration test: `sign_seal_pointer` round-trip.

Pins the canonical Seal stream-id derivation across the Seal singleton
slices: `initialize_seal` (genesis) and `sign_seal_pointer` (Live ->
Live transition) MUST land on the SAME Seal stream UUID for a given
`facility_code`. Earlier each slice inlined its own
`_seal_stream_id` helper with diverging namespace UUIDs; this test
catches a regression where any Seal slice drifts off the canonical
`seal_stream_id` helper.

Two-event lifecycle under real Postgres:

  1. `initialize_seal` writes `SealInitialized` (+ `DecisionRegistered`
     audit) and seeds `proj_federation_seal_summary` at sequence 0.
  2. `sign_seal_pointer` writes `SealPointerSigned`, advancing the
     projection's `current_head_hash` and `current_sequence_number`.

Asserts the projection reflects both writes AND that the two events
land on the same Seal stream (one Seal row per facility, both events
attached to that stream).
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation.aggregates.credential import CredentialPurpose, CredentialStatus
from cora.federation.aggregates.facility._stream_id import facility_stream_id
from cora.federation.aggregates.seal import SealStatus, load_seal
from cora.federation.aggregates.seal._stream_id import seal_stream_id
from cora.federation.features import initialize_seal, sign_seal_pointer
from cora.federation.features.initialize_seal import InitializeSeal
from cora.federation.features.sign_seal_pointer import SignSealPointer
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

_INIT_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_SIGN_NOW = _INIT_NOW + timedelta(minutes=5)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed501")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed502")
_ONLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0a2")
_OFFLINE_KEY_REF = UUID("01900000-0000-7000-8000-00000000c0b2")
_HEAD_HASH = "a" * 64
_SEQUENCE_NUMBER = 1


def _init_command(*, facility_code: str) -> InitializeSeal:
    return InitializeSeal(
        facility_code=facility_code,
        online_credential_id=_ONLINE_KEY_REF,
        offline_credential_id=_OFFLINE_KEY_REF,
    )


def _facility_lookup_for(facility_code: str) -> InMemoryFacilityLookup:
    """Seed the self-Facility row with both seal-slot credentials as
    trust anchors (Slice 6 Sub-Slice C structural set-membership check)."""
    lookup = InMemoryFacilityLookup()
    lookup.register(
        facility_id=facility_stream_id(FacilityCode(facility_code)),
        code=facility_code,
        kind="Site",
        trust_anchor_credential_ids=frozenset({_ONLINE_KEY_REF, _OFFLINE_KEY_REF}),
    )
    return lookup


def _credential_lookup_for(facility_code: str) -> InMemoryCredentialLookup:
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


def _sign_command(*, facility_code: str) -> SignSealPointer:
    return SignSealPointer(
        facility_code=facility_code,
        new_head_hash=_HEAD_HASH,
        new_sequence_number=_SEQUENCE_NUMBER,
    )


@pytest.mark.integration
async def test_sign_seal_pointer_roundtrip_lands_on_same_stream(
    db_pool: asyncpg.Pool,
) -> None:
    facility_code = f"aps-2bm-{uuid4().hex[:8]}"
    expected_stream_id = seal_stream_id(facility_code)

    init_deps = build_postgres_deps(
        db_pool,
        now=_INIT_NOW,
        ids=[uuid4() for _ in range(5)],
        credential_lookup=_credential_lookup_for(facility_code),
        facility_lookup=_facility_lookup_for(facility_code),
    )
    init_stream_id = await initialize_seal.bind(init_deps)(
        _init_command(facility_code=facility_code),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert init_stream_id == expected_stream_id

    sign_deps = build_postgres_deps(
        db_pool,
        now=_SIGN_NOW,
        ids=[uuid4() for _ in range(3)],
        facility_lookup=_facility_lookup_for(facility_code),
    )
    await sign_seal_pointer.bind(sign_deps)(
        _sign_command(facility_code=facility_code),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    seal = await load_seal(sign_deps.event_store, expected_stream_id)
    assert seal is not None
    assert seal.facility_code.value == facility_code
    assert seal.status is SealStatus.LIVE
    assert seal.current_head_hash == _HEAD_HASH
    assert seal.current_sequence_number == _SEQUENCE_NUMBER

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT event_type
              FROM events
             WHERE stream_type = 'Seal' AND stream_id = $1
             ORDER BY position
            """,
            expected_stream_id,
        )
    event_types = [r["event_type"] for r in rows]
    assert event_types == ["SealInitialized", "SealPointerSigned"], event_types

    registry = ProjectionRegistry()
    registry.register(SealSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=2.0)

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT facility_id, current_head_hash, current_sequence_number,
                   last_signed_by, last_signed_at, status
              FROM proj_federation_seal_summary
             WHERE facility_id = $1
            """,
            facility_code,
        )
    assert row is not None
    assert row["facility_id"] == facility_code
    assert row["current_head_hash"] == _HEAD_HASH
    assert row["current_sequence_number"] == _SEQUENCE_NUMBER
    assert row["last_signed_by"] == _PRINCIPAL_ID
    assert row["last_signed_at"] == _SIGN_NOW
    assert row["status"] == SealStatus.LIVE.value

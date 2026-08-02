"""End-to-end PG integration test: `define_permit` cross-BC atomic write.

Pins the cross-BC, two-stream atomic-write contract under real
Postgres. `define_permit` writes BOTH a `PermitDefined` event on
the Permit stream AND a `DecisionRegistered` audit event on the
Decision stream in ONE transaction via `EventStore.append_streams`.

Mirrors the `define_agent` cross-BC precedent (which writes
`ActorRegisteredV2` on the Access stream the same way). Differs in
that the Decision audit gets its own fresh stream id (vs the
shared-id pattern define_agent uses); cross-stream correlation lands
in `DecisionRegistered.choice = str(permit_id)`.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

import asyncpg
import pytest

from cora.federation.aggregates.permit import (
    AbiTier,
    Direction,
    OnwardActionScope,
    OutboundTerms,
    PermitStatus,
    ReadScope,
    ScopeRef,
    load_permit,
)
from cora.federation.features import define_permit
from cora.federation.features.define_permit import DefinePermit
from cora.federation.projections import PermitSummaryProjection
from cora.infrastructure.projection import ProjectionRegistry, drain_projections
from tests._drain import drain_deadline_s
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)
_EXPIRES_AT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000fed001")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-000000fed002")
_CREDENTIAL_ID = UUID("01900000-0000-7000-8000-000000fed003")


def _command() -> DefinePermit:
    return DefinePermit(
        peer_facility_code="aps-2bm",
        direction=Direction.OUTBOUND,
        allowed_credential_ids=frozenset({_CREDENTIAL_ID}),
        allowed_payload_types=frozenset({"application/json"}),
        allowed_artifact_kinds=frozenset({"dataset"}),
        abi_tier_floor=AbiTier.STABLE,
        expires_at=_EXPIRES_AT,
        terms=OutboundTerms(
            scopes=frozenset({ScopeRef(kind="dataset", name="public", qualifier=None)}),
            read_scope=ReadScope.READ_ALL_ARTIFACTS,
            onward_action_scope=OnwardActionScope.READ_ONLY,
        ),
    )


@pytest.mark.integration
async def test_define_permit_writes_both_streams_atomically(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])

    permit_id = await define_permit.bind(deps)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    # Permit stream populated; status reaches Defined via the genesis event.
    permit = await load_permit(deps.event_store, permit_id)
    assert permit is not None
    assert permit.id == permit_id
    assert permit.status is PermitStatus.DEFINED
    assert permit.peer_facility_code.value == "aps-2bm"
    assert permit.direction is Direction.OUTBOUND
    assert isinstance(permit.terms, OutboundTerms)


@pytest.mark.integration
async def test_define_permit_shared_xid8_across_streams(
    db_pool: asyncpg.Pool,
) -> None:
    """Both events MUST land in the same Postgres transaction (shared xid8).

    The events table has a `transaction_id xid8` column populated by
    `pg_current_xact_id()` on insert. Successful `append_streams`
    inserts every event in one transaction, so the Permit + Decision
    rows share the same `transaction_id`.
    """
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])

    permit_id = await define_permit.bind(deps)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT stream_type, transaction_id::text AS xid, payload
              FROM events
             WHERE (stream_type = 'Permit' AND stream_id = $1)
                OR (stream_type = 'Decision' AND payload->>'choice' = $2)
             ORDER BY position
            """,
            permit_id,
            str(permit_id),
        )

    stream_types = {r["stream_type"] for r in rows}
    assert stream_types == {"Permit", "Decision"}, stream_types
    xids = {r["xid"] for r in rows}
    assert len(xids) == 1, f"expected shared xid8 across streams, got {xids}"


@pytest.mark.integration
async def test_define_permit_projection_lands_row(
    db_pool: asyncpg.Pool,
) -> None:
    """After draining projections, proj_federation_permit_summary should
    carry the new row with status='Defined' and the genesis terms columns."""
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[uuid4() for _ in range(5)])

    permit_id = await define_permit.bind(deps)(
        _command(),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    registry = ProjectionRegistry()
    registry.register(PermitSummaryProjection())
    await drain_projections(db_pool, registry, deadline_seconds=drain_deadline_s())

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT permit_id, peer_facility_id, direction, status, terms_kind,
                   abi_tier_floor, defined_by, defined_at,
                   activated_at, suspended_at, resumed_at, revoked_at
              FROM proj_federation_permit_summary
             WHERE permit_id = $1
            """,
            permit_id,
        )
    assert row is not None
    assert row["permit_id"] == permit_id
    assert row["peer_facility_id"] == "aps-2bm"
    assert row["direction"] == Direction.OUTBOUND.value
    assert row["status"] == PermitStatus.DEFINED.value
    assert row["terms_kind"] == "Outbound"
    assert row["abi_tier_floor"] == AbiTier.STABLE.value
    assert row["defined_by"] == _PRINCIPAL_ID
    assert row["defined_at"] == _NOW
    assert row["activated_at"] is None
    assert row["suspended_at"] is None
    assert row["resumed_at"] is None
    assert row["revoked_at"] is None

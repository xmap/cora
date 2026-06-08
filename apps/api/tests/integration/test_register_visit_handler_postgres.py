"""End-to-end integration test: register_visit handler against real Postgres.

Pins the jsonb round-trip + ON CONFLICT + unique-constraint behavior for
the genesis (create-style) Visit slice. Mirrors
`test_define_policy_handler_postgres.py` shape.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import pytest

from cora.shared.identifier import Identifier
from cora.trust.aggregates.visit import VisitType
from cora.trust.features import register_visit
from cora.trust.features.register_visit import RegisterVisit
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 27, 12, 0, 0, tzinfo=UTC)
_VISIT_ID = UUID("01900000-0000-7000-8000-00000c0f1001")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0f1101")
_POLICY_ID = UUID("01900000-0000-7000-8000-00000c0f1002")
_SURFACE_ID = UUID("01900000-0000-7000-8000-00000c0f1003")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_PLANNED_END = _NOW + timedelta(hours=8)


@pytest.mark.integration
async def test_handler_persists_visit_registered_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_EVENT_ID])
    handler = register_visit.bind(deps)

    returned = await handler(
        RegisterVisit(
            visit_id=_VISIT_ID,
            policy_id=_POLICY_ID,
            surface_id=_SURFACE_ID,
            type=VisitType.USER,
            planned_start_at=_NOW,
            planned_end_at=_PLANNED_END,
            external_refs=frozenset({Identifier(scheme="proposal", value="12345")}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert returned == _VISIT_ID

    events, version = await deps.event_store.load("Visit", _VISIT_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "VisitRegistered"
    assert stored.schema_version == 1
    assert stored.payload["visit_id"] == str(_VISIT_ID)
    assert stored.payload["policy_id"] == str(_POLICY_ID)
    assert stored.payload["surface_id"] == str(_SURFACE_ID)
    assert stored.payload["type"] == "user"
    assert stored.payload["planned_start_at"] == _NOW.isoformat()
    assert stored.payload["planned_end_at"] == _PLANNED_END.isoformat()
    assert stored.payload["parent_id"] is None
    assert stored.payload["external_refs"] == [{"scheme": "proposal", "value": "12345"}]
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "RegisterVisit"}
    assert stored.occurred_at == _NOW
    assert stored.position > 0

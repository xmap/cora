"""End-to-end integration test: define_family handler against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features import define_family
from cora.equipment.features.define_family import DefineFamily
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_FAMILY_NAME = "Continuous Rotation Tomography"
# The stream id is derived from the name; the generator supplies only
# the per-event id.
_DERIVED_ID = family_stream_id(FamilyName(_FAMILY_NAME))
_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ca0e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_family_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_EVENT_ID])

    family_id = await define_family.bind(deps)(
        DefineFamily(name=_FAMILY_NAME, affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert family_id == _DERIVED_ID

    events, version = await deps.event_store.load("Family", _DERIVED_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "FamilyDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "family_id": str(_DERIVED_ID),
        "name": "Continuous Rotation Tomography",
        # empty. Pinned by tests/unit/equipment/test_family_events.py.
        "affordances": [],
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineFamily"}
    assert stored.occurred_at == _NOW

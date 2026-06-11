"""End-to-end integration test: define_role handler against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.family import Affordance
from cora.equipment.aggregates.role import SEED_ROLE_IMAGER_ID
from cora.equipment.features import define_role
from cora.equipment.features.define_role import DefineRole
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
# The handler derives the stream_id deterministically from the name
# (role_stream_id(RoleName("Imager")) = uuid5(_ROLE_NAMESPACE, "imager")
# = SEED_ROLE_IMAGER_ID), so the returned id is the pinned seed id, not
# an IdGenerator value. The generator supplies only the event_id.
_NEW_ID = SEED_ROLE_IMAGER_ID
_EVENT_ID = UUID("01900000-0000-7000-8000-00000074ca0e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_define_role_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_EVENT_ID])

    role_id = await define_role.bind(deps)(
        DefineRole(
            name="Imager",
            docstring="Acquires 2D image frames on exposure or trigger.",
            required_affordances=frozenset({Affordance.IMAGEABLE}),
            optional_affordances=frozenset({Affordance.BINNABLE}),
            produces=frozenset({"Image"}),
            consumes=frozenset({"TriggerIn"}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert role_id == _NEW_ID

    events, version = await deps.event_store.load("Role", _NEW_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "RoleDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "role_id": str(_NEW_ID),
        "name": "Imager",
        "docstring": "Acquires 2D image frames on exposure or trigger.",
        "occurred_at": _NOW.isoformat(),
        "required_affordances": ["Imageable"],
        "optional_affordances": ["Binnable"],
        "produces": ["Image"],
        "consumes": ["TriggerIn"],
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefineRole"}
    assert stored.occurred_at == _NOW

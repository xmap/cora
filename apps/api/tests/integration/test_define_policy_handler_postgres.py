"""End-to-end integration test: define_policy handler against real Postgres.

Mirrors `test_define_conduit_handler_postgres.py`. Proves the bare
handler composes with PostgresEventStore: the serialized payload —
including the sorted permission lists — survives jsonb round-trip
and the event lands under stream_type='Policy' with the right shape.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.infrastructure.routing import SYSTEM_HTTP_SURFACE_ID
from cora.trust.features import define_policy
from cora.trust.features.define_policy import DefinePolicy
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000c0c0fa1")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000c0c0fb1")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_CONDUIT_ID = UUID("01900000-0000-7000-8000-00000000aaaa")
_ALLOWED_PRINCIPAL = UUID("01900000-0000-7000-8000-000000000a01")


@pytest.mark.integration
async def test_handler_persists_policy_defined_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(db_pool, now=_NOW, ids=[_NEW_ID, _EVENT_ID])
    handler = define_policy.bind(deps)

    policy_id = await handler(
        DefinePolicy(
            name="Beam-team",
            conduit_id=_CONDUIT_ID,
            permitted_principal_ids=frozenset({_ALLOWED_PRINCIPAL}),
            permitted_commands=frozenset({"RegisterActor"}),
            surface_id=SYSTEM_HTTP_SURFACE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert policy_id == _NEW_ID

    events, version = await deps.event_store.load("Policy", _NEW_ID)
    assert version == 1
    assert len(events) == 1

    stored = events[0]
    assert stored.event_type == "PolicyDefined"
    assert stored.schema_version == 1
    assert stored.payload == {
        "policy_id": str(_NEW_ID),
        "name": "Beam-team",
        "conduit_id": str(_CONDUIT_ID),
        "surface_id": str(SYSTEM_HTTP_SURFACE_ID),
        "permitted_principal_ids": [str(_ALLOWED_PRINCIPAL)],
        "permitted_commands": ["RegisterActor"],
        "occurred_at": _NOW.isoformat(),
    }
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.causation_id is None
    assert stored.event_id == _EVENT_ID
    assert stored.metadata == {"command": "DefinePolicy"}
    assert stored.occurred_at == _NOW
    assert stored.position > 0

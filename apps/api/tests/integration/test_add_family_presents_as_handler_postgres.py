"""End-to-end integration test: add_family_presents_as handler against real Postgres.

Exercises the full flow: a Family is seeded via direct event-store
append (skipping the define_family handler so no FamilyDefined
projection apply is required), a Role is seeded into
`InMemoryRoleLookup` (the integration deps default), and
`add_family_presents_as.bind(deps)` is invoked. The committed event
is read back from the Postgres event store.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.family import (
    Affordance,
    FamilyDefined,
    event_type_name,
    to_payload,
)
from cora.equipment.features import add_family_presents_as
from cora.equipment.features.add_family_presents_as import AddFamilyPresentsAs
from cora.infrastructure.event_envelope import to_new_event
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_FAMILY_ID = UUID("01900000-0000-7000-8000-00000074fb01")
_ROLE_ID = UUID("01900000-0000-7000-8000-00000074fb02")
_SEED_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000074fa00")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-00000074fb04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_add_family_presents_as_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[_ADD_EVENT_ID],
    )

    # Seed the Camera Family via direct event append (skips
    # define_family handler authz + idempotency).
    genesis = FamilyDefined(
        family_id=_FAMILY_ID,
        name="Camera",
        occurred_at=_NOW,
        affordances=frozenset({Affordance.IMAGEABLE}),
    )
    await deps.event_store.append(
        stream_type="Family",
        stream_id=_FAMILY_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_SEED_GENESIS_EVENT_ID,
                command_name="DefineFamily",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )

    # Seed the Detector Role into the in-memory RoleLookup adapter.
    lookup = deps.role_lookup
    assert hasattr(lookup, "register")
    lookup.register(  # type: ignore[union-attr]
        role_id=_ROLE_ID,
        name="Detector",
        required_affordances=frozenset({"Imageable"}),
    )

    await add_family_presents_as.bind(deps)(
        AddFamilyPresentsAs(family_id=_FAMILY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Family", _FAMILY_ID)
    assert version == 2
    add_event = events[-1]
    assert add_event.event_type == "FamilyPresentsAsAdded"
    assert add_event.payload == {
        "family_id": str(_FAMILY_ID),
        "role_id": str(_ROLE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert add_event.event_id == _ADD_EVENT_ID
    assert add_event.metadata == {"command": "AddFamilyPresentsAs"}

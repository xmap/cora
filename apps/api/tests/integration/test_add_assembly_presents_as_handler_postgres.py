"""End-to-end integration test: add_assembly_presents_as handler against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.assembly import (
    AssemblyDefined,
    AssemblyName,
    event_type_name,
    to_payload,
)
from cora.equipment.features import add_assembly_presents_as
from cora.equipment.features.add_assembly_presents_as import AddAssemblyPresentsAs
from cora.infrastructure.event_envelope import to_new_event
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000084fb01")
_ROLE_ID = UUID("01900000-0000-7000-8000-00000084fb03")
_SEED_GENESIS_EVENT_ID = UUID("01900000-0000-7000-8000-00000084fa00")
_ADD_EVENT_ID = UUID("01900000-0000-7000-8000-00000084fb04")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_add_assembly_presents_as_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[_ADD_EVENT_ID],
    )

    # Seed Assembly via direct event-store append (skips
    # define_assembly handler).
    genesis = AssemblyDefined(
        assembly_id=_ASSEMBLY_ID,
        name=AssemblyName("Microscope"),
        presents_as=frozenset(),
        required_slots=frozenset(),
        required_wires=frozenset(),
        parameter_overrides_schema=None,
        drawing=None,
        version=None,
        content_hash="abc",
        occurred_at=_NOW,
    )
    await deps.event_store.append(
        stream_type="Assembly",
        stream_id=_ASSEMBLY_ID,
        expected_version=0,
        events=[
            to_new_event(
                event_type=event_type_name(genesis),
                payload=to_payload(genesis),
                occurred_at=genesis.occurred_at,
                event_id=_SEED_GENESIS_EVENT_ID,
                command_name="DefineAssembly",
                correlation_id=_CORRELATION_ID,
                causation_id=None,
                principal_id=_PRINCIPAL_ID,
            )
        ],
    )

    # Seed Role into in-memory RoleLookup adapter.
    lookup = deps.role_lookup
    assert hasattr(lookup, "register")
    lookup.register(  # type: ignore[union-attr]
        role_id=_ROLE_ID,
        name="Detector",
        required_affordances=frozenset({"Imageable"}),
    )

    await add_assembly_presents_as.bind(deps)(
        AddAssemblyPresentsAs(assembly_id=_ASSEMBLY_ID, role_id=_ROLE_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Assembly", _ASSEMBLY_ID)
    assert version == 2
    add_event = events[-1]
    assert add_event.event_type == "AssemblyPresentsAsAdded"
    assert add_event.payload == {
        "assembly_id": str(_ASSEMBLY_ID),
        "role_id": str(_ROLE_ID),
        "occurred_at": _NOW.isoformat(),
    }
    assert add_event.event_id == _ADD_EVENT_ID
    assert add_event.metadata == {"command": "AddAssemblyPresentsAs"}

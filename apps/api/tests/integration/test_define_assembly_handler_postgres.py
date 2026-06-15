"""End-to-end integration test: define_assembly handler against real Postgres.

Mirrors `test_define_family_handler_postgres.py`. The Assembly stream
emits one AssemblyDefined event; the handler resolves each presented
Role via the RoleLookup port before appending, then persists the event
to the Postgres pool.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.role import SEED_ROLE_DETECTOR_ID
from cora.equipment.features import define_assembly
from cora.equipment.features.define_assembly import DefineAssembly
from cora.infrastructure.adapters.in_memory_role_lookup import InMemoryRoleLookup
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054cb02")
_ASSEMBLY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb1e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000bb")


@pytest.mark.integration
async def test_define_assembly_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_DETECTOR_ID, "Detector")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _ASSEMBLY_ID,
            _ASSEMBLY_EVENT_ID,
        ],
        role_lookup=role_lookup,
    )

    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(
            name="Microscope",
            presents_as=frozenset({SEED_ROLE_DETECTOR_ID}),
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert assembly_id == _ASSEMBLY_ID

    events, version = await deps.event_store.load("Assembly", _ASSEMBLY_ID)
    assert version == 1
    assert len(events) == 1
    stored = events[0]
    assert stored.event_type == "AssemblyDefined"
    assert stored.schema_version == 1
    payload = stored.payload
    assert payload["assembly_id"] == str(_ASSEMBLY_ID)
    assert payload["name"] == "Microscope"
    assert payload["presents_as"] == [str(SEED_ROLE_DETECTOR_ID)]
    assert payload["required_slots"] == []
    assert payload["required_wires"] == []
    assert payload["parameter_overrides_schema"] is None
    assert payload["drawing"] is None
    assert payload["version"] is None
    assert len(payload["content_hash"]) == 64
    assert stored.correlation_id == _CORRELATION_ID
    assert stored.event_id == _ASSEMBLY_EVENT_ID
    assert stored.metadata == {"command": "DefineAssembly"}
    assert stored.occurred_at == _NOW

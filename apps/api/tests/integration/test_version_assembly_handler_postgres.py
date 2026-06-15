"""End-to-end integration test: version_assembly handler against Postgres.

The Assembly stream accumulates one AssemblyDefined event followed
by one AssemblyVersioned event. The handler resolves each presented
Role via the RoleLookup port, then appends at the captured
optimistic-concurrency version.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.role import SEED_ROLE_DETECTOR_ID
from cora.equipment.features import define_assembly, version_assembly
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.version_assembly import VersionAssembly
from cora.infrastructure.adapters.in_memory_role_lookup import InMemoryRoleLookup
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 14, 0, 0, tzinfo=UTC)
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054cd02")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cd1e")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cd2e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000cc")


@pytest.mark.integration
async def test_version_assembly_appends_versioned_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    role_lookup = InMemoryRoleLookup()
    role_lookup.register(SEED_ROLE_DETECTOR_ID, "Detector")
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _ASSEMBLY_ID,
            _DEFINED_EVENT_ID,
            _VERSIONED_EVENT_ID,
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

    await version_assembly.bind(deps)(
        VersionAssembly(
            assembly_id=assembly_id,
            name="Microscope-rev2",
            presents_as=frozenset({SEED_ROLE_DETECTOR_ID}),
            version="v0.2.0",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Assembly", assembly_id)
    assert version == 2
    assert len(events) == 2
    defined_event = events[0]
    versioned_event = events[1]
    assert defined_event.event_type == "AssemblyDefined"
    assert versioned_event.event_type == "AssemblyVersioned"
    assert versioned_event.event_id == _VERSIONED_EVENT_ID

    versioned_payload = versioned_event.payload
    assert versioned_payload["assembly_id"] == str(assembly_id)
    assert versioned_payload["name"] == "Microscope-rev2"
    assert versioned_payload["presents_as"] == [str(SEED_ROLE_DETECTOR_ID)]
    assert versioned_payload["version"] == "v0.2.0"
    assert versioned_payload["previous_content_hash"] == defined_event.payload["content_hash"]
    assert len(versioned_payload["content_hash"]) == 64
    assert versioned_event.metadata == {"command": "VersionAssembly"}
    assert versioned_event.occurred_at == _NOW

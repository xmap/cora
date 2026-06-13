"""End-to-end integration test: version_assembly handler against Postgres.

The Assembly stream accumulates one AssemblyDefined event followed
by one AssemblyVersioned event. The handler verifies the Family
referenced by `presents_as_family_id` still resolves, then appends
at the captured optimistic-concurrency version.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.features import define_assembly, define_family, version_assembly
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.version_assembly import VersionAssembly
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 14, 0, 0, tzinfo=UTC)
_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cd0e")
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054cd02")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cd1e")
_VERSIONED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cd2e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000cc")


@pytest.mark.integration
async def test_version_assembly_appends_versioned_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _FAMILY_EVENT_ID,
            _ASSEMBLY_ID,
            _DEFINED_EVENT_ID,
            _VERSIONED_EVENT_ID,
        ],
    )

    family_id = await define_family.bind(deps)(
        DefineFamily(name="Detector", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(name="MCTOptics", presents_as_family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await version_assembly.bind(deps)(
        VersionAssembly(
            assembly_id=assembly_id,
            name="MCTOptics-rev2",
            presents_as_family_id=family_id,
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
    assert versioned_payload["name"] == "MCTOptics-rev2"
    assert versioned_payload["presents_as_family_id"] == str(family_id)
    assert versioned_payload["version"] == "v0.2.0"
    assert versioned_payload["previous_content_hash"] == defined_event.payload["content_hash"]
    assert len(versioned_payload["content_hash"]) == 64
    assert versioned_event.metadata == {"command": "VersionAssembly"}
    assert versioned_event.occurred_at == _NOW

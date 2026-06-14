"""End-to-end integration test: define_assembly handler against real Postgres.

Mirrors `test_define_family_handler_postgres.py`. The Assembly stream
emits one AssemblyDefined event; the handler verifies the
presents_as_family_id resolves before appending (so a prior
FamilyDefined event must exist in the same Postgres pool).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.family import FamilyName, family_stream_id
from cora.equipment.features import define_assembly, define_family
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_FAMILY_ID = family_stream_id(FamilyName("Detector"))
_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb0e")
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054cb02")
_ASSEMBLY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054cb1e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000bb")


@pytest.mark.integration
async def test_define_assembly_persists_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _FAMILY_EVENT_ID,
            _ASSEMBLY_ID,
            _ASSEMBLY_EVENT_ID,
        ],
    )

    family_id = await define_family.bind(deps)(
        DefineFamily(name="Detector", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert family_id == _FAMILY_ID

    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(name="Microscope", presents_as_family_id=family_id),
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
    assert payload["presents_as_family_id"] == str(_FAMILY_ID)
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

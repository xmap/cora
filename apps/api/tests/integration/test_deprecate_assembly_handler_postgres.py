"""End-to-end integration test: deprecate_assembly handler against Postgres.

The Assembly stream accumulates AssemblyDefined followed by
AssemblyDeprecated. The handler captures the optimistic-concurrency
version from a single event-store load and appends the terminal
event.
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.features import (
    define_assembly,
    define_family,
    deprecate_assembly,
    version_assembly,
)
from cora.equipment.features.define_assembly import DefineAssembly
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.deprecate_assembly import DeprecateAssembly
from cora.equipment.features.version_assembly import VersionAssembly
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 6, 3, 14, 0, 0, tzinfo=UTC)
_FAMILY_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ce0e")
_ASSEMBLY_ID = UUID("01900000-0000-7000-8000-00000054ce02")
_DEFINED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ce1e")
_DEPRECATED_EVENT_ID = UUID("01900000-0000-7000-8000-00000054ce2e")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000dd")


@pytest.mark.integration
async def test_deprecate_assembly_appends_deprecated_event_to_postgres(
    db_pool: asyncpg.Pool,
) -> None:
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _FAMILY_EVENT_ID,
            _ASSEMBLY_ID,
            _DEFINED_EVENT_ID,
            _DEPRECATED_EVENT_ID,
        ],
    )

    await define_family.bind(deps)(
        DefineFamily(name="Detector", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(name="Microscope", presents_as=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    await deprecate_assembly.bind(deps)(
        DeprecateAssembly(assembly_id=assembly_id, reason="superseded by rev2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Assembly", assembly_id)
    assert version == 2
    assert len(events) == 2
    deprecated = events[1]
    assert deprecated.event_type == "AssemblyDeprecated"
    assert deprecated.event_id == _DEPRECATED_EVENT_ID
    assert deprecated.payload == {
        "assembly_id": str(assembly_id),
        "reason": "superseded by rev2",
        "occurred_at": _NOW.isoformat(),
    }
    assert deprecated.correlation_id == _CORRELATION_ID
    assert deprecated.metadata == {"command": "DeprecateAssembly"}
    assert deprecated.occurred_at == _NOW


_FAMILY_EVENT_ID_V = UUID("01900000-0000-7000-8000-00000054cf0e")
_ASSEMBLY_ID_V = UUID("01900000-0000-7000-8000-00000054cf02")
_DEFINED_EVENT_ID_V = UUID("01900000-0000-7000-8000-00000054cf1e")
_VERSIONED_EVENT_ID_V = UUID("01900000-0000-7000-8000-00000054cf2e")
_DEPRECATED_EVENT_ID_V = UUID("01900000-0000-7000-8000-00000054cf3e")


@pytest.mark.integration
async def test_deprecate_assembly_persists_through_versioned_arm(
    db_pool: asyncpg.Pool,
) -> None:
    """Multi-source FSM: Versioned -> Deprecated. Locks that the
    handler's expected_version capture works after version_assembly
    has already appended one event on top of define."""
    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            _FAMILY_EVENT_ID_V,
            _ASSEMBLY_ID_V,
            _DEFINED_EVENT_ID_V,
            _VERSIONED_EVENT_ID_V,
            _DEPRECATED_EVENT_ID_V,
        ],
    )

    await define_family.bind(deps)(
        DefineFamily(name="Detector", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assembly_id = await define_assembly.bind(deps)(
        DefineAssembly(name="Microscope", presents_as=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_assembly.bind(deps)(
        VersionAssembly(
            assembly_id=assembly_id,
            name="Microscope",
            presents_as=frozenset(),
            version="v1",
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_assembly.bind(deps)(
        DeprecateAssembly(assembly_id=assembly_id, reason="end-of-life"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Assembly", assembly_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "AssemblyDefined",
        "AssemblyVersioned",
        "AssemblyDeprecated",
    ]
    assert events[2].event_id == _DEPRECATED_EVENT_ID_V
    assert events[2].payload["reason"] == "end-of-life"

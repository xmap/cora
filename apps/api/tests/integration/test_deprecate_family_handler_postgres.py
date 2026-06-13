"""End-to-end integration test: deprecate_family against real Postgres.

Round-trip: define + version + deprecate + load_family returns
the deprecated state with version preserved (the audit
signal of the last revision before deprecation).
"""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.equipment.aggregates.family import (
    FamilyName,
    FamilyStatus,
    family_stream_id,
    load_family,
)
from cora.equipment.features import (
    define_family,
    deprecate_family,
    version_family,
)
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.deprecate_family import DeprecateFamily
from cora.equipment.features.version_family import VersionFamily
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_deprecate_family_persists_and_preserves_version_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    family_id = family_stream_id(FamilyName("X-ray Fluorescence Mapping"))
    defined_event_id = UUID("01900000-0000-7000-8000-00000057fb0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-00000057fb0f")
    deprecated_event_id = UUID("01900000-0000-7000-8000-00000057fb10")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[
            defined_event_id,
            versioned_event_id,
            deprecated_event_id,
        ],
    )

    await define_family.bind(deps)(
        DefineFamily(name="X-ray Fluorescence Mapping", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_family.bind(deps)(
        VersionFamily(family_id=family_id, version_tag="2026-Q2", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_family.bind(deps)(
        DeprecateFamily(family_id=family_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Family", family_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "FamilyDefined",
        "FamilyVersioned",
        "FamilyDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == deprecated_event_id

    state = await load_family(deps.event_store, family_id)
    assert state is not None
    assert state.status is FamilyStatus.DEPRECATED
    # Audit signal: latest version_tag preserved through deprecation.
    assert state.version == "2026-Q2"

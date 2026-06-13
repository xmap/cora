"""End-to-end integration test: version_family against real Postgres.

Round-trip: define + version + load_family returns the
versioned state with version set.
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
from cora.equipment.features import define_family, version_family
from cora.equipment.features.define_family import DefineFamily
from cora.equipment.features.version_family import VersionFamily
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_version_family_persists_event_and_round_trips_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    family_id = family_stream_id(FamilyName("X-ray Fluorescence Mapping"))
    defined_event_id = UUID("01900000-0000-7000-8000-00000057fa0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-00000057fa0f")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[defined_event_id, versioned_event_id],
    )

    await define_family.bind(deps)(
        DefineFamily(name="X-ray Fluorescence Mapping", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_family.bind(deps)(
        VersionFamily(family_id=family_id, version_tag="2026-Q3", affordances=frozenset()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Family", family_id)
    assert version == 2
    assert [e.event_type for e in events] == [
        "FamilyDefined",
        "FamilyVersioned",
    ]
    versioned = events[1]
    assert versioned.event_id == versioned_event_id
    assert versioned.metadata == {"command": "VersionFamily"}
    assert versioned.payload["version_tag"] == "2026-Q3"

    state = await load_family(deps.event_store, family_id)
    assert state is not None
    assert state.name == FamilyName("X-ray Fluorescence Mapping")
    assert state.status is FamilyStatus.VERSIONED
    assert state.version == "2026-Q3"

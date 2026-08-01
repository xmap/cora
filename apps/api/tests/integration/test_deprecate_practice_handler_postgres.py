"""End-to-end integration test: deprecate_practice against real Postgres."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
import pytest

from cora.recipe.aggregates.practice import PracticeStatus, load_practice
from cora.recipe.features import (
    define_practice,
    deprecate_practice,
    version_practice,
)
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.deprecate_practice import DeprecatePractice
from cora.recipe.features.version_practice import VersionPractice
from cora.shared.deprecation import DeprecationReason
from tests.integration._helpers import build_postgres_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")


@pytest.mark.integration
async def test_deprecate_practice_persists_and_preserves_version_through_fold(
    db_pool: asyncpg.Pool,
) -> None:
    practice_id = UUID("01900000-0000-7000-8000-0000005afb01")
    defined_event_id = UUID("01900000-0000-7000-8000-0000005afb0e")
    versioned_event_id = UUID("01900000-0000-7000-8000-0000005afb0f")
    deprecated_event_id = UUID("01900000-0000-7000-8000-0000005afb10")

    deps = build_postgres_deps(
        db_pool,
        now=_NOW,
        ids=[practice_id, defined_event_id, versioned_event_id, deprecated_event_id],
    )

    await define_practice.bind(deps)(
        DefinePractice(name="X", method_id=UUID(int=1), site_id=UUID(int=2)),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await version_practice.bind(deps)(
        VersionPractice(practice_id=practice_id, version_tag="2026-Q2"),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    await deprecate_practice.bind(deps)(
        DeprecatePractice(reason=DeprecationReason.SUPERSEDED, practice_id=practice_id),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    events, version = await deps.event_store.load("Practice", practice_id)
    assert version == 3
    assert [e.event_type for e in events] == [
        "PracticeDefined",
        "PracticeVersioned",
        "PracticeDeprecated",
    ]
    deprecated = events[2]
    assert deprecated.event_id == deprecated_event_id

    state = await load_practice(deps.event_store, practice_id)
    assert state is not None
    assert state.status is PracticeStatus.DEPRECATED
    # Audit signal preserved.
    assert state.version == "2026-Q2"
